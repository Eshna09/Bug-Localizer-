"""
Evaluation metrics for bug localization research.

Computes:
  - Top-1, Top-3, Top-5 Accuracy
  - MRR (Mean Reciprocal Rank)
  - Precision, Recall
  - File-level and function-level accuracy
  - Retrieval Recall@K

CRITICAL: Ground truth is only accessed HERE, AFTER predictions are generated.
The localization models never see ground truth during prediction.
"""
from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional

from core.models import (
    LocalizationApproach,
    LocalizationResult,
    PredictedLocation,
    RetrievedChunkDetail,
    EvaluationRecord,
    EvaluationSummary,
)

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    """Normalize file path for comparison."""
    return path.replace("\\", "/").removeprefix("./").strip("/")


def _paths_match(path_a: str, path_b: str) -> bool:
    normalized_a = _normalize_path(path_a)
    normalized_b = _normalize_path(path_b)
    return (
        normalized_a == normalized_b
        or normalized_a.endswith(f"/{normalized_b}")
        or normalized_b.endswith(f"/{normalized_a}")
    )


def _location_matches(pred: PredictedLocation, gt_file: str, gt_function: str) -> bool:
    """Check if a prediction matches ground truth at function level."""
    return _paths_match(pred.file, gt_file) and pred.function == gt_function


def _file_matches(pred: PredictedLocation, gt_file: str) -> bool:
    """Check if a prediction matches ground truth at file level."""
    return _paths_match(pred.file, gt_file)


def _chunk_matches(chunk: RetrievedChunkDetail, gt_file: str, gt_function: str) -> bool:
    return _paths_match(chunk.file, gt_file) and chunk.function == gt_function


def _compute_reciprocal_rank(
    predictions: List[PredictedLocation],
    gt_file: str,
    gt_function: str,
) -> float:
    for pred in predictions:
        if _location_matches(pred, gt_file, gt_function):
            return 1.0 / pred.rank
    return 0.0


class EvaluationEngine:
    """
    Computes evaluation metrics by comparing localization predictions
    against ground truth from the bug dataset.

    Ground truth is ONLY accessed here, AFTER all predictions are generated.
    """

    def evaluate_single(
        self,
        bug_id: str,
        approach: LocalizationApproach,
        predictions: List[PredictedLocation],
        ground_truth_file: str,
        ground_truth_function: str,
        category: str = "",
        difficulty: str = "",
        issue_quality: str = "",
        scope: str = "",
        issue_type: str = "",
        retrieved_chunks: Optional[List[RetrievedChunkDetail]] = None,
        rejected_prediction_count: int = 0,
        latency_ms: Optional[float] = None,
        token_count: Optional[int] = None,
        cpu_avg_percent: Optional[float] = None,
        memory_peak_mb: Optional[float] = None,
        test_passed: Optional[bool] = None,
    ) -> EvaluationRecord:
        """Evaluate one approach's predictions for one bug."""
        top1 = any(
            _location_matches(p, ground_truth_file, ground_truth_function)
            for p in predictions[:1]
        )
        top3 = any(
            _location_matches(p, ground_truth_file, ground_truth_function)
            for p in predictions[:3]
        )
        top5 = any(
            _location_matches(p, ground_truth_file, ground_truth_function)
            for p in predictions[:5]
        )
        rr = _compute_reciprocal_rank(predictions, ground_truth_file, ground_truth_function)
        file_top1 = any(
            _file_matches(p, ground_truth_file)
            for p in predictions[:1]
        )
        retrieval_hit = None
        if approach == LocalizationApproach.RAG_LLM and retrieved_chunks is not None:
            retrieval_hit = any(
                _chunk_matches(chunk, ground_truth_file, ground_truth_function)
                for chunk in retrieved_chunks
            )

        return EvaluationRecord(
            bug_id=bug_id,
            ground_truth_file=ground_truth_file,
            ground_truth_function=ground_truth_function,
            approach=approach,
            predictions=predictions,
            category=category,
            difficulty=difficulty,
            issue_quality=issue_quality,
            scope=scope,
            issue_type=issue_type,
            top1_correct=top1,
            top3_correct=top3,
            top5_correct=top5,
            reciprocal_rank=rr,
            file_level_top1=file_top1,
            retrieval_hit=retrieval_hit,
            rejected_prediction_count=rejected_prediction_count,
            latency_ms=latency_ms,
            token_count=token_count,
            cpu_avg_percent=cpu_avg_percent,
            memory_peak_mb=memory_peak_mb,
            test_passed=test_passed,
        )

    def summarize(
        self,
        approach: LocalizationApproach,
        records: List[EvaluationRecord],
    ) -> EvaluationSummary:
        """Aggregate evaluation records into a summary."""
        n = len(records)
        if n == 0:
            return EvaluationSummary(
                approach=approach,
                total_bugs=0,
                top1_accuracy=0.0,
                top3_accuracy=0.0,
                top5_accuracy=0.0,
                mrr=0.0,
                file_level_top1=0.0,
                precision=None,
                recall=None,
                f1_score=None,
                retrieval_recall_at_k=None,
                hallucination_rate=None,
                avg_latency_ms=None,
                avg_tokens=None,
                avg_cpu_percent=None,
                peak_memory_mb=None,
                test_pass_rate=None,
                records=[],
            )

        top1 = sum(r.top1_correct for r in records) / n
        top3 = sum(r.top3_correct for r in records) / n
        top5 = sum(r.top5_correct for r in records) / n
        mrr = sum(r.reciprocal_rank for r in records) / n
        file_top1 = sum(r.file_level_top1 for r in records) / n
        prediction_count = sum(len(r.predictions) for r in records)
        correct_prediction_count = sum(
            _location_matches(prediction, r.ground_truth_file, r.ground_truth_function)
            for r in records
            for prediction in r.predictions
        )
        precision = correct_prediction_count / prediction_count if prediction_count else None
        recall = sum(
            any(
                _location_matches(prediction, r.ground_truth_file, r.ground_truth_function)
                for prediction in r.predictions
            )
            for r in records
        ) / n
        f1_score = (
            2 * precision * recall / (precision + recall)
            if precision is not None and precision + recall
            else 0.0 if precision is not None else None
        )
        retrieval_records = [r for r in records if r.retrieval_hit is not None]
        retrieval_recall = (
            sum(r.retrieval_hit is True for r in retrieval_records) / len(retrieval_records)
            if retrieval_records
            else None
        )
        total_rejected = sum(r.rejected_prediction_count for r in records)
        total_candidates = prediction_count + total_rejected
        hallucination_rate = total_rejected / total_candidates if total_candidates else None

        def average_available(values: List[Optional[float]]) -> Optional[float]:
            available = [value for value in values if value is not None]
            return round(sum(available) / len(available), 4) if available else None

        token_average = average_available([
            float(r.token_count) if r.token_count is not None else None for r in records
        ])
        test_records = [r.test_passed for r in records if r.test_passed is not None]

        return EvaluationSummary(
            approach=approach,
            total_bugs=n,
            top1_accuracy=round(top1, 4),
            top3_accuracy=round(top3, 4),
            top5_accuracy=round(top5, 4),
            mrr=round(mrr, 4),
            file_level_top1=round(file_top1, 4),
            precision=round(precision, 4) if precision is not None else None,
            recall=round(recall, 4),
            f1_score=round(f1_score, 4) if f1_score is not None else None,
            retrieval_recall_at_k=round(retrieval_recall, 4) if retrieval_recall is not None else None,
            hallucination_rate=round(hallucination_rate, 4) if hallucination_rate is not None else None,
            avg_latency_ms=average_available([r.latency_ms for r in records]),
            avg_tokens=token_average,
            avg_cpu_percent=average_available([r.cpu_avg_percent for r in records]),
            peak_memory_mb=max(
                (r.memory_peak_mb for r in records if r.memory_peak_mb is not None),
                default=None,
            ),
            test_pass_rate=(
                round(sum(test_records) / len(test_records), 4)
                if test_records
                else None
            ),
            records=records,
        )

    def compare_approaches(
        self,
        summaries: List[EvaluationSummary],
    ) -> Dict[str, Any]:
        """
        Compare all approaches and return a structured comparison.
        Rankings are based on Top-1 Accuracy, with MRR as tiebreaker.
        """
        ranked = sorted(
            (summary for summary in summaries if summary.total_bugs > 0),
            key=lambda s: (s.top1_accuracy, s.mrr),
            reverse=True,
        )
        return {
            "ranked": [
                {
                    "rank": i + 1,
                    "approach": s.approach.value,
                    "top1_accuracy": s.top1_accuracy,
                    "top3_accuracy": s.top3_accuracy,
                    "top5_accuracy": s.top5_accuracy,
                    "mrr": s.mrr,
                    "file_level_top1": s.file_level_top1,
                    "total_bugs": s.total_bugs,
                }
                for i, s in enumerate(ranked)
            ]
        }
