"""
Main analysis pipeline orchestrator.

Execution order (important for Ollama single-threaded model):
  2A: Clone + parse  → collect RepoStats
  2B-non-LLM: Keyword + Structural (instant, no Ollama)
  2B-embed:   Build FAISS index with nomic-embed-text FIRST
  2B-llm:     LLM-Only localization (Ollama, one call)
  2B-rag:     RAG+LLM localization (Ollama, one call)
  2C:         Explanation (Ollama, one call)
  2D:         Fix generation (Ollama, one call)
  2E:         Verification (Docker, optional)

Running embed before any LLM call prevents Ollama deadlock when using
a single-threaded local model server.

DESIGN INVARIANTS:
  - Localization predictions recorded BEFORE explanation/fix.
  - Ground truth NEVER accessed here.
  - Original repository NEVER modified.
  - Repository code NEVER executed on host.
  - Test files are NEVER ranked as primary root cause.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.models import AnalysisResult, AnalysisStatus, LocalizationResult, PredictedLocation, RepoStats
from core.ingestion import clone_repository, scan_source_files, _detect_language
from core.parser import MultiFileParser
from localization import (
    KeywordSearchLocalizer,
    StructuralAnalysisLocalizer,
    LLMOnlyLocalizer,
    RAGLLMLocalizer,
)
from localization.embeddings import CodeVectorStore
from localization.file_classifier import is_test_file, is_source_file
from explanation import BugExplainer
from fix import FixGenerator
from verification import VerificationSandbox
from config.settings import settings

logger = logging.getLogger(__name__)


def _rank_primary_predictions(
    approach_results: list[Optional[LocalizationResult]],
) -> list[PredictedLocation]:
    """Rank source locations by reciprocal-rank consensus across approaches."""
    candidates: dict[tuple[str, str], dict] = {}
    for approach_index, localization in enumerate(approach_results):
        if not localization:
            continue
        for prediction in localization.predictions:
            if prediction.is_test_file:
                continue
            file_path = prediction.file.replace("\\", "/").strip("/").lower()
            key = (file_path, prediction.function.lower())
            entry = candidates.setdefault(key, {
                "prediction": prediction,
                "score": 0.0,
                "support": 0,
                "best_rank": prediction.rank,
                "first_approach": approach_index,
            })
            entry["score"] += 1 / max(prediction.rank, 1)
            entry["support"] += 1
            if prediction.rank < entry["best_rank"]:
                entry["prediction"] = prediction
                entry["best_rank"] = prediction.rank

    ranked = sorted(
        candidates.values(),
        key=lambda entry: (
            -entry["score"],
            -entry["support"],
            entry["best_rank"],
            entry["first_approach"],
        ),
    )
    return [
        entry["prediction"].model_copy(update={"rank": rank})
        for rank, entry in enumerate(ranked, start=1)
    ]


def _build_repo_stats(
    repo_url: str,
    commit_hash: str,
    language: str,
    source_files: list,
    functions: list,
    indexed_chunks: int,
    repo_root: Path,
) -> RepoStats:
    """Collect repository statistics from scanned files and parsed functions."""
    source_count = sum(1 for f in source_files if is_source_file(str(f)))
    test_count   = sum(1 for f in source_files if is_test_file(str(f)))

    fn_files = {u.file_path for u in functions}
    class_names = {u.class_name for u in functions if u.class_name}
    all_deps: set = set()
    for u in functions:
        all_deps.update(u.calls)

    # Count languages by file extension
    lang_counts: dict[str, int] = {}
    for f in source_files:
        ext = Path(str(f)).suffix.lower()
        lang_counts[ext] = lang_counts.get(ext, 0) + 1

    return RepoStats(
        repo_url=repo_url,
        commit_hash=commit_hash,
        detected_language=language,
        total_files=len(source_files),
        source_files=source_count,
        test_files=test_count,
        total_functions=len(functions),
        total_classes=len(class_names),
        total_dependencies=len(all_deps),
        code_chunks=len(functions),
        indexed_chunks=indexed_chunks,
        languages=lang_counts,
    )


class BugLocalizerPipeline:

    def __init__(self):
        self._keyword_localizer    = KeywordSearchLocalizer()
        self._structural_localizer = StructuralAnalysisLocalizer()
        self._llm_only_localizer   = LLMOnlyLocalizer()
        self._explainer            = BugExplainer()
        self._fix_generator        = FixGenerator()
        self._sandbox              = VerificationSandbox()

    def analyze(
        self,
        repo_url: str,
        issue_text: str,
        issue_id: Optional[str] = None,
        run_verification: bool = True,
    ) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        issue_id    = issue_id or analysis_id[:8]
        timestamp   = datetime.now(timezone.utc).isoformat()

        logger.info("=== Starting analysis %s ===", analysis_id)
        logger.info("Repository: %s", repo_url)
        logger.info("Issue: %s", issue_text[:100])

        result = AnalysisResult(
            analysis_id=analysis_id,
            status=AnalysisStatus.RUNNING,
            repo_url=repo_url,
            commit_hash="",
            detected_language="",
            issue_description=issue_text,
            timestamp=timestamp,
        )

        # ── 2A: Clone + parse ────────────────────────────────────────────
        try:
            local_path, commit_hash = clone_repository(repo_url)
            result.commit_hash = commit_hash
        except ValueError as exc:
            err_str = str(exc)
            if "Repository not found" in err_str or "exit code(128)" in err_str:
                err_str = (f"Repository not found: {repo_url}. "
                           "Make sure the URL is correct and the repository is public.")
            result.status = AnalysisStatus.FAILED
            result.error  = err_str
            return result

        try:
            repo_root    = Path(local_path)
            language     = _detect_language(repo_root)
            result.detected_language = language
            source_files = scan_source_files(local_path, language)
            if not source_files:
                result.status = AnalysisStatus.FAILED
                result.error  = f"No source files found for language: {language}"
                return result
            parser    = MultiFileParser(language=language)
            functions = parser.parse_repository(source_files, repo_root)
            if not functions:
                result.status = AnalysisStatus.FAILED
                result.error  = "No functions could be parsed."
                return result
            logger.info("Parsed %d functions from %d files", len(functions), len(source_files))
        except Exception as exc:
            result.status = AnalysisStatus.FAILED
            result.error  = f"Repository parsing failed: {exc}"
            return result

        # ── 2B-A: Keyword Search (no Ollama) ─────────────────────────────
        try:
            result.keyword_result = self._keyword_localizer.localize(
                issue_id=issue_id, issue_text=issue_text, functions=functions,
                repo_url=repo_url, commit_hash=commit_hash,
                top_k=settings.rag_top_k,
            )
            logger.info("[Keyword] Done: %d predictions", len(result.keyword_result.predictions))
        except Exception as exc:
            logger.error("[Keyword] Failed: %s", exc)

        # ── 2B-B: Structural Analysis (no Ollama) ────────────────────────
        try:
            result.structural_result = self._structural_localizer.localize(
                issue_id=issue_id, issue_text=issue_text, functions=functions,
                repo_url=repo_url, commit_hash=commit_hash,
                top_k=settings.rag_top_k,
            )
            logger.info("[Structural] Done: %d predictions", len(result.structural_result.predictions))
        except Exception as exc:
            logger.error("[Structural] Failed: %s", exc)

        # ── 2B-D (part 1): Build FAISS index BEFORE any LLM calls ───────
        vector_store = CodeVectorStore(model_name=settings.embedding_model)
        indexed_chunks = 0
        try:
            logger.info("[Embedding] Building FAISS index for %d functions...", len(functions))
            vector_store.build(functions)
            indexed_chunks = vector_store.size
            logger.info("[Embedding] FAISS index ready: %d chunks", indexed_chunks)
        except Exception as exc:
            logger.error("[Embedding] Failed: %s", exc)

        # ── Collect RepoStats (after index is built) ──────────────────────
        try:
            result.repo_stats = _build_repo_stats(
                repo_url=repo_url,
                commit_hash=commit_hash,
                language=language,
                source_files=source_files,
                functions=functions,
                indexed_chunks=indexed_chunks,
                repo_root=repo_root,
            )
        except Exception as exc:
            logger.warning("[RepoStats] Failed to collect: %s", exc)

        # ── 2B-C: LLM Only (Ollama call 1) ──────────────────────────────
        try:
            logger.info("[LLM-Only] Starting...")
            result.llm_only_result = self._llm_only_localizer.localize(
                issue_id=issue_id, issue_text=issue_text, functions=functions,
                repo_url=repo_url, commit_hash=commit_hash,
                top_k=settings.rag_top_k,
            )
            logger.info(
                "[LLM-Only] Done: %d predictions, status=%s",
                len(result.llm_only_result.predictions),
                result.llm_only_result.status,
            )
        except Exception as exc:
            logger.error("[LLM-Only] Failed: %s", exc)

        # ── 2B-D (part 2): RAG + LLM (Ollama call 2) ────────────────────
        try:
            if vector_store.size > 0:
                logger.info("[RAG+LLM] Starting...")
                rag_localizer = RAGLLMLocalizer(vector_store=vector_store)
                result.rag_llm_result = rag_localizer.localize(
                    issue_id=issue_id, issue_text=issue_text, functions=functions,
                    repo_url=repo_url, commit_hash=commit_hash,
                    top_k=settings.rag_top_k,
                )
                logger.info(
                    "[RAG+LLM] Done: %d predictions, status=%s",
                    len(result.rag_llm_result.predictions),
                    result.rag_llm_result.status,
                )
            else:
                logger.warning("[RAG+LLM] Skipped — vector store empty")
        except Exception as exc:
            logger.error("[RAG+LLM] Failed: %s", exc)

        # ── Primary predictions: combine evidence across approaches ───────
        primary = _rank_primary_predictions([
            result.keyword_result,
            result.structural_result,
            result.llm_only_result,
            result.rag_llm_result,
        ])

        if not primary:
            result.status = AnalysisStatus.COMPLETED
            result.error  = "All localization approaches returned empty predictions."
            return result

        result.primary_predictions = primary

        # ── 2C: Explanation (Ollama call 3) ──────────────────────────────
        try:
            logger.info("[Explanation] Generating...")
            result.bug_explanation = self._explainer.explain(
                issue_text=issue_text,
                predictions=result.primary_predictions,
                functions=functions,
            )
            logger.info("[Explanation] Done")
        except Exception as exc:
            logger.error("[Explanation] Failed: %s", exc)

        # ── 2D: Fix Generation (Ollama call 4) ───────────────────────────
        if result.primary_predictions:
            try:
                logger.info("[Fix] Generating...")
                result.proposed_fix = self._fix_generator.generate(
                    issue_text=issue_text,
                    top_prediction=result.primary_predictions[0],
                    explanation=result.bug_explanation,
                    functions=functions,
                )
                logger.info("[Fix] Done")
            except Exception as exc:
                logger.error("[Fix] Failed: %s", exc)

        # ── 2E: Verification (Docker, optional) ──────────────────────────
        if run_verification and result.proposed_fix:
            try:
                result.verification = self._sandbox.verify(
                    repo_path=local_path,
                    fix=result.proposed_fix,
                    language=language,
                )
            except Exception as exc:
                logger.error("[Verification] Failed: %s", exc)

        result.status = AnalysisStatus.COMPLETED
        logger.info("=== Analysis %s completed ===", analysis_id)
        return result
