"""
Approach B — Structural / Dependency Analysis Localization.

Pipeline:
  Issue → keyword extraction → find seed functions (source files only) →
  expand via call graph (callers + callees) → rank by dependency centrality

No LLM used.
Test files are EXCLUDED from seed selection and primary candidates.
They appear only as SUPPORTING EVIDENCE when structurally connected.
"""
from __future__ import annotations
import logging
import time
from collections import defaultdict, deque
from typing import List, Dict, Set

from core.models import (
    FunctionUnit,
    LocalizationApproach,
    LocalizationResult,
    PredictedLocation,
    EvidenceStrength,
)
from localization.keyword import _extract_keywords, _score_function
from localization.file_classifier import is_test_file, is_source_file

logger = logging.getLogger(__name__)


def _build_call_graph(functions: List[FunctionUnit]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = defaultdict(set)
    name_to_ids: Dict[str, List[str]] = defaultdict(list)

    for unit in functions:
        name_to_ids[unit.function_name].append(unit.chunk_id)

    for unit in functions:
        for called_name in unit.calls:
            for target_id in name_to_ids.get(called_name, []):
                graph[unit.chunk_id].add(target_id)

    return graph


def _bfs_neighbors(
    seed_ids: Set[str],
    graph: Dict[str, Set[str]],
    reverse_graph: Dict[str, Set[str]],
    depth: int = 2,
) -> Dict[str, int]:
    distances: Dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()

    for sid in seed_ids:
        distances[sid] = 0
        queue.append((sid, 0))

    while queue:
        node, dist = queue.popleft()
        if dist >= depth:
            continue
        neighbors = graph.get(node, set()) | reverse_graph.get(node, set())
        for neighbor in neighbors:
            if neighbor not in distances:
                distances[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    return distances


def _evidence_from_structural(distance: int, seed_score: float) -> EvidenceStrength:
    if distance == 0 and seed_score > 0:
        return EvidenceStrength.HIGH
    if distance == 0:
        return EvidenceStrength.MEDIUM
    if distance == 1 and seed_score > 0:
        return EvidenceStrength.MEDIUM
    if distance <= 2:
        return EvidenceStrength.LOW
    return EvidenceStrength.INSUFFICIENT


class StructuralAnalysisLocalizer:
    """
    Approach B: structural/dependency analysis, no LLM.

    Seeds are ONLY seeded from production source files.
    The BFS expansion may reach test files; they are kept as supporting evidence.
    """

    def localize(
        self,
        issue_id: str,
        issue_text: str,
        functions: List[FunctionUnit],
        repo_url: str,
        commit_hash: str,
        top_k: int = 5,
    ) -> LocalizationResult:
        start = time.time()

        keywords = _extract_keywords(issue_text)
        logger.info("[Structural] Keywords: %s", keywords)

        # Step 1: Score only SOURCE functions for seed selection
        source_functions = [u for u in functions if is_source_file(u.file_path)]
        all_functions_map: Dict[str, FunctionUnit] = {u.chunk_id: u for u in functions}

        if not source_functions:
            elapsed = (time.time() - start) * 1000
            return LocalizationResult(
                approach=LocalizationApproach.STRUCTURAL,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                latency_ms=elapsed,
                status="EMPTY_RESPONSE",
                error="No production source functions found for structural seed selection.",
            )

        scored: list[tuple[float, FunctionUnit]] = []
        for unit in source_functions:
            score = _score_function(unit, keywords)
            scored.append((score, unit))
        scored.sort(key=lambda x: x[0], reverse=True)

        max_score = scored[0][0] if scored else 0.0

        # Seed set: top scoring SOURCE functions only
        seed_threshold = max_score * 0.3 if max_score > 0 else 0
        seed_ids: Set[str] = {
            unit.chunk_id for score, unit in scored
            if score >= seed_threshold and score > 0
        }
        logger.info("[Structural] %d seed nodes (source-only)", len(seed_ids))

        if not seed_ids:
            elapsed = (time.time() - start) * 1000
            return LocalizationResult(
                approach=LocalizationApproach.STRUCTURAL,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                latency_ms=elapsed,
                status="EMPTY_RESPONSE",
                error="No seed functions found for structural expansion.",
            )

        # Step 2: Build call graph across ALL functions (source + test)
        graph = _build_call_graph(functions)
        reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        for src, targets in graph.items():
            for tgt in targets:
                reverse_graph[tgt].add(src)

        # Step 3: BFS expansion
        distances = _bfs_neighbors(seed_ids, graph, reverse_graph, depth=3)

        # Step 4: Score = keyword_score / (distance + 1)
        source_candidates: list[tuple[float, int, FunctionUnit]] = []
        test_candidates:   list[tuple[float, int, FunctionUnit]] = []

        for chunk_id, dist in distances.items():
            unit = all_functions_map.get(chunk_id)
            if not unit:
                continue
            kw_score = _score_function(unit, keywords)
            combined = (kw_score + 1.0) / (dist + 1)
            if is_source_file(unit.file_path):
                source_candidates.append((combined, dist, unit))
            else:
                test_candidates.append((combined, dist, unit))

        source_candidates.sort(key=lambda x: x[0], reverse=True)
        test_candidates.sort(key=lambda x: x[0], reverse=True)

        predictions: List[PredictedLocation] = []

        # PRIMARY: source file candidates
        for rank, (score, dist, unit) in enumerate(source_candidates[:top_k], start=1):
            proximity = "direct match" if dist == 0 else f"dependency distance {dist}"
            reason = (
                f"Structural analysis: {proximity}. "
                f"Keyword score: {_score_function(unit, keywords):.1f}. "
                f"Called by: {unit.called_by[:3] or 'none'}. "
                f"Calls: {unit.calls[:3] or 'none'}."
            )
            predictions.append(PredictedLocation(
                rank=rank,
                file=unit.file_path,
                function=unit.function_name,
                class_name=unit.class_name,
                line_start=unit.start_line,
                line_end=unit.end_line,
                reason=reason,
                evidence_strength=_evidence_from_structural(
                    dist, _score_function(unit, keywords)
                ),
                source_code=unit.source_code,
                is_test_file=False,
                candidate_type="primary",
            ))

        # SUPPORTING EVIDENCE: test file candidates
        for rank, (score, dist, unit) in enumerate(
            test_candidates[:3], start=len(predictions) + 1
        ):
            proximity = "direct match" if dist == 0 else f"dependency distance {dist}"
            reason = (
                f"TEST FILE — supporting evidence. Structural {proximity}. "
                f"Keyword score: {_score_function(unit, keywords):.1f}."
            )
            predictions.append(PredictedLocation(
                rank=rank,
                file=unit.file_path,
                function=unit.function_name,
                class_name=unit.class_name,
                line_start=unit.start_line,
                line_end=unit.end_line,
                reason=reason,
                evidence_strength=_evidence_from_structural(
                    dist, _score_function(unit, keywords)
                ),
                source_code=unit.source_code,
                is_test_file=True,
                candidate_type="supporting_evidence",
            ))

        elapsed = (time.time() - start) * 1000
        logger.info(
            "[Structural] %d primary + %d supporting in %.1f ms",
            len([p for p in predictions if not p.is_test_file]),
            len([p for p in predictions if p.is_test_file]),
            elapsed,
        )

        status = "SUCCESS" if predictions else "EMPTY_RESPONSE"

        return LocalizationResult(
            approach=LocalizationApproach.STRUCTURAL,
            issue_id=issue_id,
            repository=repo_url,
            commit_hash=commit_hash,
            predictions=predictions,
            latency_ms=elapsed,
            status=status,
        )
