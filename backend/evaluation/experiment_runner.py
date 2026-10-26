"""
Experiment runner.
Executes all four localization approaches over a bug dataset and
computes evaluation metrics.

GROUND TRUTH SEPARATION:
  Ground truth is only accessed HERE, after predictions are generated.
  The localization pipeline never sees the ground truth.
"""
from __future__ import annotations
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.models import (
    LocalizationApproach,
    LocalizationResult,
    EvaluationRecord,
    EvaluationSummary,
)
from core.ingestion import clone_repository, scan_source_files, _detect_language
from core.parser import MultiFileParser
from localization import (
    KeywordSearchLocalizer,
    StructuralAnalysisLocalizer,
    LLMOnlyLocalizer,
    RAGLLMLocalizer,
)
from localization.embeddings import CodeVectorStore
from evaluation.metrics import EvaluationEngine
from config.settings import settings
from localization.resource_monitor import run_with_resources

logger = logging.getLogger(__name__)


@dataclass
class BugEntry:
    """One entry from the bug dataset (ground truth)."""
    bug_id: str
    repo_url: str
    issue_description: str
    ground_truth_file: str
    ground_truth_function: str
    category: str = ""
    difficulty: str = ""
    issue_quality: str = ""
    scope: str = ""
    issue_type: str = ""
    commit_hash: Optional[str] = None


@dataclass
class ExperimentResult:
    experiment_id: str
    bug_id: str
    approach: LocalizationApproach
    localization_result: LocalizationResult
    evaluation_record: EvaluationRecord
    latency_ms: float


def load_bug_dataset(path: str, default_repo_url: Optional[str] = None) -> List[BugEntry]:
    """
    Load a bug dataset from a JSON file.
    Expected format: list of dicts with keys matching BugEntry fields.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError("Bug dataset must be a JSON array.")

    entries = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each bug dataset entry must be a JSON object.")
        required = {
            "bug_id": item.get("bug_id"),
            "repo_url": item.get("repo_url") or default_repo_url,
            "issue_description": item.get("issue_description") or item.get("issue_report"),
            "ground_truth_file": item.get("ground_truth_file") or item.get("root_cause_file"),
            "ground_truth_function": item.get("ground_truth_function") or item.get("root_cause_function"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Bug dataset entry {item.get('bug_id', '<unknown>')} is missing required fields: "
                f"{', '.join(missing)}."
            )
        entries.append(BugEntry(
            bug_id=required["bug_id"],
            repo_url=required["repo_url"],
            issue_description=required["issue_description"],
            ground_truth_file=required["ground_truth_file"],
            ground_truth_function=required["ground_truth_function"],
            category=item.get("category", ""),
            difficulty=item.get("difficulty", ""),
            issue_quality=item.get("issue_quality") or item.get("issue_report_quality", ""),
            scope=item.get("scope", ""),
            issue_type=item.get("issue_type", ""),
            commit_hash=item.get("commit_hash"),
        ))
    return entries


class ExperimentRunner:
    """
    Runs the full localization experiment over a bug dataset.
    """

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self._keyword = KeywordSearchLocalizer()
        self._structural = StructuralAnalysisLocalizer()
        self._llm_only = LLMOnlyLocalizer()
        self._engine = EvaluationEngine()
        self._rag_localizers: Dict[str, RAGLLMLocalizer] = {}

    def run(
        self,
        dataset_path: str,
        approaches: Optional[List[str]] = None,
        default_repo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run experiment. Returns summary of results for all approaches.
        """
        approaches = approaches or ["keyword", "structural", "llm_only", "rag_llm"]
        experiment_id = str(uuid.uuid4())
        dataset = load_bug_dataset(dataset_path, default_repo_url=default_repo_url)
        logger.info("Running experiment %s over %d bugs", experiment_id, len(dataset))

        # Per-approach records
        records: Dict[str, List[EvaluationRecord]] = {a: [] for a in approaches}
        repositories: Dict[str, tuple[str, str, list]] = {}

        for bug in dataset:
            logger.info("Processing bug: %s", bug.bug_id)
            try:
                if bug.repo_url not in repositories:
                    local_path, commit_hash = clone_repository(bug.repo_url)
                    repo_root = Path(local_path)
                    language = _detect_language(repo_root)
                    source_files = scan_source_files(local_path, language)
                    parser = MultiFileParser(language=language)
                    functions = parser.parse_repository(source_files, repo_root)
                    repositories[bug.repo_url] = (local_path, commit_hash, functions)
                local_path, commit_hash, functions = repositories[bug.repo_url]
                bug.commit_hash = commit_hash

                if not functions:
                    logger.warning("No functions for bug %s", bug.bug_id)
                    continue

                # Run each enabled approach
                for approach_name in approaches:
                    loc_result, resource_usage = run_with_resources(
                        self._run_approach,
                        approach_name,
                        bug,
                        functions,
                        local_path,
                        commit_hash,
                    )
                    if loc_result is None:
                        continue
                    loc_result.resource_usage = resource_usage

                    # Evaluate predictions against ground truth (ONLY HERE)
                    token_usage = loc_result.token_usage or {}
                    token_count = token_usage.get("total_tokens")
                    if token_count is None:
                        prompt_tokens = token_usage.get("prompt_tokens")
                        completion_tokens = token_usage.get("completion_tokens")
                        if prompt_tokens is not None or completion_tokens is not None:
                            token_count = (prompt_tokens or 0) + (completion_tokens or 0)
                    resource_usage = loc_result.resource_usage or {}
                    record = self._engine.evaluate_single(
                        bug_id=bug.bug_id,
                        approach=loc_result.approach,
                        predictions=loc_result.predictions,
                        ground_truth_file=bug.ground_truth_file,
                        ground_truth_function=bug.ground_truth_function,
                        category=bug.category,
                        difficulty=bug.difficulty,
                        issue_quality=bug.issue_quality,
                        scope=bug.scope,
                        issue_type=bug.issue_type,
                        retrieved_chunks=(
                            loc_result.retrieved_chunk_details
                            [:self.top_k]
                            if approach_name == "rag_llm"
                            and "vector_retrieval" in loc_result.pipeline_stages
                            else None
                        ),
                        rejected_prediction_count=len(loc_result.rejected_predictions),
                        latency_ms=loc_result.latency_ms,
                        token_count=token_count,
                        cpu_avg_percent=resource_usage.get("cpu_avg_percent"),
                        memory_peak_mb=resource_usage.get("memory_rss_mb_peak"),
                    )
                    records[approach_name].append(record)

            except Exception as exc:
                logger.error("Experiment failed for bug %s: %s", bug.bug_id, exc)

        # Compute summaries
        summaries = []
        for approach_name in approaches:
            approach_enum = LocalizationApproach(approach_name)
            summary = self._engine.summarize(approach_enum, records[approach_name])
            summaries.append(summary)

        comparison = self._engine.compare_approaches(summaries)
        breakdowns = {}
        for dimension in ("category", "difficulty", "issue_quality", "scope"):
            group_value = lambda record: getattr(record, dimension) or "unspecified"
            values = sorted({
                group_value(record)
                for approach_records in records.values()
                for record in approach_records
            })
            breakdowns[dimension] = {
                value: {
                    approach_name: self._engine.summarize(
                        LocalizationApproach(approach_name),
                        [
                            record
                            for record in records[approach_name]
                            if group_value(record) == value
                        ],
                    ).model_dump(exclude={"records"})
                    for approach_name in approaches
                }
                for value in values
            }
        evaluated_bug_ids = {
            record.bug_id
            for approach_records in records.values()
            for record in approach_records
        }

        return {
            "experiment_id": experiment_id,
            "status": "completed",
            "total_bugs": len(dataset),
            "evaluated_bugs": len(evaluated_bug_ids),
            "approaches_run": approaches,
            "comparison": comparison,
            "summaries": [s.model_dump() for s in summaries],
            "breakdowns": breakdowns,
        }

    def _run_approach(
        self,
        approach_name: str,
        bug: BugEntry,
        functions,
        local_path: str,
        commit_hash: str,
    ) -> Optional[LocalizationResult]:
        try:
            if approach_name == "keyword":
                return self._keyword.localize(
                    issue_id=bug.bug_id,
                    issue_text=bug.issue_description,
                    functions=functions,
                    repo_url=bug.repo_url,
                    commit_hash=commit_hash,
                    top_k=self.top_k,
                )
            elif approach_name == "structural":
                return self._structural.localize(
                    issue_id=bug.bug_id,
                    issue_text=bug.issue_description,
                    functions=functions,
                    repo_url=bug.repo_url,
                    commit_hash=commit_hash,
                    top_k=self.top_k,
                )
            elif approach_name == "llm_only":
                return self._llm_only.localize(
                    issue_id=bug.bug_id,
                    issue_text=bug.issue_description,
                    functions=functions,
                    repo_url=bug.repo_url,
                    commit_hash=commit_hash,
                    top_k=self.top_k,
                )
            elif approach_name == "rag_llm":
                if bug.repo_url not in self._rag_localizers:
                    vector_store = CodeVectorStore(model_name=settings.embedding_model)
                    vector_store.build(functions)
                    self._rag_localizers[bug.repo_url] = RAGLLMLocalizer(
                        vector_store=vector_store
                    )
                return self._rag_localizers[bug.repo_url].localize(
                    issue_id=bug.bug_id,
                    issue_text=bug.issue_description,
                    functions=functions,
                    repo_url=bug.repo_url,
                    commit_hash=commit_hash,
                    top_k=self.top_k,
                )
            else:
                logger.warning("Unknown approach: %s", approach_name)
                return None
        except Exception as exc:
            logger.error("Approach %s failed for bug %s: %s", approach_name, bug.bug_id, exc)
            return None
