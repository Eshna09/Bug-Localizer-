import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import (
    LocalizationApproach,
    LocalizationResult,
    PredictedLocation,
    RetrievedChunkDetail,
)
from evaluation.metrics import EvaluationEngine
from pipeline import _rank_primary_predictions
from storage.database import Base, Database, EvaluationPreviewRow


def prediction(file: str, function: str, rank: int) -> PredictedLocation:
    return PredictedLocation(
        rank=rank,
        file=file,
        function=function,
        line_start=1,
        line_end=2,
        reason="test prediction",
    )


def chunk(file: str, function: str) -> RetrievedChunkDetail:
    return RetrievedChunkDetail(
        chunk_id=f"{file}:{function}",
        file=file,
        function=function,
        line_start=1,
        line_end=2,
        similarity_score=0.9,
        code_preview="",
    )


class EvaluationMetricsTests(unittest.TestCase):
    def test_evaluation_preview_survives_database_session_reopen(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        sessions = sessionmaker(bind=engine)
        preview = {"summaries": [{"approach": "rag_llm", "top1_accuracy": 0.8}]}

        try:
            with sessions() as db:
                db.add(EvaluationPreviewRow(
                    id="shopbug-demo-v1",
                    data_json=json.dumps(preview),
                ))
                db.commit()

            with sessions() as db:
                self.assertEqual(Database(db).get_evaluation_preview(), preview)
        finally:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    def test_primary_ranking_prefers_cross_approach_consensus(self):
        def result(approach, predictions):
            return LocalizationResult(
                approach=approach,
                issue_id="B1",
                repository="https://github.com/example/repo",
                commit_hash="abc",
                predictions=predictions,
            )

        conventional = prediction("app/services/checkout_service.py", "checkout", 1)
        unrelated_rag = prediction("app/main.py", "lifespan", 1)
        ranked = _rank_primary_predictions([
            result(LocalizationApproach.KEYWORD, [conventional]),
            result(LocalizationApproach.STRUCTURAL, [conventional]),
            result(LocalizationApproach.LLM_ONLY, [
                prediction("app/routes/checkout.py", "checkout", 1),
            ]),
            result(LocalizationApproach.RAG_LLM, [unrelated_rag]),
        ])

        self.assertEqual(ranked[0].file, "app/services/checkout_service.py")
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(
            [item.rank for item in ranked],
            list(range(1, len(ranked) + 1)),
        )

    def test_summarize_computes_prediction_retrieval_and_resource_metrics(self):
        engine = EvaluationEngine()
        first = engine.evaluate_single(
            bug_id="B1",
            approach=LocalizationApproach.RAG_LLM,
            predictions=[
                prediction("src/a.py", "target", 1),
                prediction("src/b.py", "other", 2),
            ],
            ground_truth_file="app/src/a.py",
            ground_truth_function="target",
            retrieved_chunks=[chunk("src/a.py", "target")],
            rejected_prediction_count=1,
            latency_ms=100,
            token_count=100,
            cpu_avg_percent=10,
            memory_peak_mb=30,
            test_passed=True,
        )
        second = engine.evaluate_single(
            bug_id="B2",
            approach=LocalizationApproach.RAG_LLM,
            predictions=[prediction("src/c.py", "other", 1)],
            ground_truth_file="src/a.py",
            ground_truth_function="target",
            retrieved_chunks=[chunk("src/z.py", "missing")],
            latency_ms=300,
            token_count=200,
            cpu_avg_percent=20,
            memory_peak_mb=40,
            test_passed=False,
        )

        summary = engine.summarize(LocalizationApproach.RAG_LLM, [first, second])

        self.assertEqual(summary.precision, 0.3333)
        self.assertEqual(summary.recall, 0.5)
        self.assertEqual(summary.f1_score, 0.4)
        self.assertEqual(summary.retrieval_recall_at_k, 0.5)
        self.assertEqual(summary.hallucination_rate, 0.25)
        self.assertEqual(summary.avg_latency_ms, 200)
        self.assertEqual(summary.avg_tokens, 150)
        self.assertEqual(summary.avg_cpu_percent, 15)
        self.assertEqual(summary.peak_memory_mb, 40)
        self.assertEqual(summary.test_pass_rate, 0.5)

    def test_unavailable_metrics_remain_none_without_measurements(self):
        summary = EvaluationEngine().summarize(LocalizationApproach.KEYWORD, [])

        self.assertIsNone(summary.precision)
        self.assertIsNone(summary.recall)
        self.assertIsNone(summary.retrieval_recall_at_k)
        self.assertIsNone(summary.hallucination_rate)
        self.assertIsNone(summary.avg_latency_ms)
        self.assertIsNone(summary.avg_tokens)
        self.assertIsNone(summary.avg_cpu_percent)
        self.assertIsNone(summary.peak_memory_mb)
        self.assertIsNone(summary.test_pass_rate)


if __name__ == "__main__":
    unittest.main()
