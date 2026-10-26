"""
Approach A — Keyword / Text Search Localization.

Pipeline:
  Issue text → keyword extraction → source-code search → rank files/functions

No LLM used.
Production source files are ranked as PRIMARY candidates.
Test/spec files that match keywords are demoted to SUPPORTING EVIDENCE.
"""
from __future__ import annotations
import logging
import re
import time
from typing import List

from core.models import (
    FunctionUnit,
    LocalizationApproach,
    LocalizationResult,
    PredictedLocation,
    EvidenceStrength,
)
from localization.file_classifier import is_test_file, is_source_file

logger = logging.getLogger(__name__)

# Words that add no signal
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "on",
    "at", "by", "for", "with", "about", "as", "into", "through", "from",
    "and", "or", "not", "no", "if", "then", "but", "so", "yet", "nor",
    "when", "where", "which", "that", "this", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "its",
    "get", "got", "getting", "set", "go", "going", "put", "take",
    "apply", "use", "using", "used", "make", "making", "made",
    "show", "showing", "see", "seeing",
    "amount", "value", "result", "output",
}


def _extract_keywords(issue_text: str) -> List[str]:
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', issue_text.lower())
    keywords = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    seen: set = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _score_function(unit: FunctionUnit, keywords: List[str]) -> float:
    score = 0.0
    fn_name_lower = unit.function_name.lower()
    file_lower = unit.file_path.lower()
    source_lower = unit.source_code.lower()

    for kw in keywords:
        if kw in fn_name_lower:
            score += 3.0
        if kw in file_lower:
            score += 2.0
        if kw in source_lower:
            score += 1.0

    return score


def _evidence_from_score(score: float, max_score: float) -> EvidenceStrength:
    if max_score == 0:
        return EvidenceStrength.INSUFFICIENT
    ratio = score / max_score
    if ratio >= 0.7:
        return EvidenceStrength.HIGH
    if ratio >= 0.4:
        return EvidenceStrength.MEDIUM
    if ratio > 0:
        return EvidenceStrength.LOW
    return EvidenceStrength.INSUFFICIENT


class KeywordSearchLocalizer:
    """
    Approach A: pure keyword/text search, no LLM.

    PRIMARY candidates  → production source files only.
    SUPPORTING EVIDENCE → test/spec files that matched keywords (shown separately).
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
        logger.info("[Keyword] Extracted keywords: %s", keywords)

        if not keywords:
            elapsed = (time.time() - start) * 1000
            return LocalizationResult(
                approach=LocalizationApproach.KEYWORD,
                issue_id=issue_id,
                repository=repo_url,
                commit_hash=commit_hash,
                predictions=[],
                latency_ms=elapsed,
                status="EMPTY_RESPONSE",
                error="No meaningful keywords could be extracted from the issue.",
            )

        # Score every function
        all_scored: list[tuple[float, FunctionUnit]] = []
        for unit in functions:
            score = _score_function(unit, keywords)
            if score > 0:
                all_scored.append((score, unit))

        all_scored.sort(key=lambda x: x[0], reverse=True)

        # Split into source (primary) and test (supporting)
        source_scored = [(s, u) for s, u in all_scored if is_source_file(u.file_path)]
        test_scored   = [(s, u) for s, u in all_scored if is_test_file(u.file_path)]

        max_score = source_scored[0][0] if source_scored else (all_scored[0][0] if all_scored else 0.0)

        predictions: List[PredictedLocation] = []
        # PRIMARY: production files
        for rank, (score, unit) in enumerate(source_scored[:top_k], start=1):
            matched_kws = [
                kw for kw in keywords
                if kw in (unit.function_name + unit.file_path + unit.source_code).lower()
            ]
            reason = f"Matched keywords: {', '.join(matched_kws[:8])}. Score: {score:.1f}."
            predictions.append(PredictedLocation(
                rank=rank,
                file=unit.file_path,
                function=unit.function_name,
                class_name=unit.class_name,
                line_start=unit.start_line,
                line_end=unit.end_line,
                reason=reason,
                evidence_strength=_evidence_from_score(score, max_score),
                source_code=unit.source_code,
                is_test_file=False,
                candidate_type="primary",
            ))

        # SUPPORTING EVIDENCE: test files (up to 3, appended after primary)
        test_max = test_scored[0][0] if test_scored else 0.0
        for rank, (score, unit) in enumerate(test_scored[:3], start=len(predictions) + 1):
            matched_kws = [
                kw for kw in keywords
                if kw in (unit.function_name + unit.file_path + unit.source_code).lower()
            ]
            reason = (
                f"TEST FILE — supporting evidence only. "
                f"Matched keywords: {', '.join(matched_kws[:6])}. Score: {score:.1f}."
            )
            predictions.append(PredictedLocation(
                rank=rank,
                file=unit.file_path,
                function=unit.function_name,
                class_name=unit.class_name,
                line_start=unit.start_line,
                line_end=unit.end_line,
                reason=reason,
                evidence_strength=_evidence_from_score(score, test_max),
                source_code=unit.source_code,
                is_test_file=True,
                candidate_type="supporting_evidence",
            ))

        elapsed = (time.time() - start) * 1000
        logger.info(
            "[Keyword] %d primary + %d supporting in %.1f ms",
            len([p for p in predictions if not p.is_test_file]),
            len([p for p in predictions if p.is_test_file]),
            elapsed,
        )

        status = "SUCCESS" if predictions else "EMPTY_RESPONSE"

        return LocalizationResult(
            approach=LocalizationApproach.KEYWORD,
            issue_id=issue_id,
            repository=repo_url,
            commit_hash=commit_hash,
            predictions=predictions,
            latency_ms=elapsed,
            status=status,
        )
