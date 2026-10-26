"""Illustrative evaluation data persisted for the dashboard preview."""

DEMO_SUMMARIES = [
    {
        "approach": "keyword",
        "top1_accuracy": 0.4,
        "top3_accuracy": 0.6,
        "top5_accuracy": 0.7,
        "mrr": 0.51,
        "file_level_top1": 0.5,
        "precision": 0.34,
        "recall": 0.7,
        "f1_score": 0.46,
        "retrieval_recall_at_k": None,
        "hallucination_rate": 0.18,
        "avg_latency_ms": 1200,
        "avg_tokens": 0,
        "avg_cpu_percent": 18,
        "peak_memory_mb": 90,
        "test_pass_rate": 0.3,
        "total_bugs": 20,
    },
    {
        "approach": "structural",
        "top1_accuracy": 0.5,
        "top3_accuracy": 0.7,
        "top5_accuracy": 0.8,
        "mrr": 0.62,
        "file_level_top1": 0.6,
        "precision": 0.4,
        "recall": 0.8,
        "f1_score": 0.53,
        "retrieval_recall_at_k": None,
        "hallucination_rate": 0.12,
        "avg_latency_ms": 1000,
        "avg_tokens": 0,
        "avg_cpu_percent": 15,
        "peak_memory_mb": 85,
        "test_pass_rate": 0.4,
        "total_bugs": 20,
    },
    {
        "approach": "llm_only",
        "top1_accuracy": 0.6,
        "top3_accuracy": 0.8,
        "top5_accuracy": 0.9,
        "mrr": 0.72,
        "file_level_top1": 0.7,
        "precision": 0.45,
        "recall": 0.9,
        "f1_score": 0.6,
        "retrieval_recall_at_k": None,
        "hallucination_rate": 0.08,
        "avg_latency_ms": 900,
        "avg_tokens": 780,
        "avg_cpu_percent": 12,
        "peak_memory_mb": 80,
        "test_pass_rate": 0.55,
        "total_bugs": 20,
    },
    {
        "approach": "rag_llm",
        "top1_accuracy": 0.8,
        "top3_accuracy": 0.9,
        "top5_accuracy": 1,
        "mrr": 0.86,
        "file_level_top1": 0.85,
        "precision": 0.5,
        "recall": 1,
        "f1_score": 0.67,
        "retrieval_recall_at_k": 1,
        "hallucination_rate": 0.02,
        "avg_latency_ms": 700,
        "avg_tokens": 620,
        "avg_cpu_percent": 9,
        "peak_memory_mb": 70,
        "test_pass_rate": 0.8,
        "total_bugs": 20,
    },
]

_BREAKDOWN_GROUPS = {
    "category": [
        ("Calculation", 4),
        ("Authentication", 4),
        ("Cart", 1),
        ("Database", 2),
        ("Page Failure", 1),
        ("Input Validation", 1),
        ("UI Rendering", 1),
        ("Backend Logic", 2),
        ("Navigation", 1),
        ("Dependency", 1),
        ("State Management", 1),
        ("Frontend Logic", 1),
    ],
    "difficulty": [("Easy", 8), ("Medium", 7), ("Hard", 5)],
    "issue_quality": [("Specific", 6), ("Moderate", 6), ("Vague", 8)],
    "scope": [("Single-file", 10), ("Multi-file", 5), ("Unspecified", 5)],
}


def _build_breakdowns() -> dict:
    breakdowns = {}
    for dimension, groups in _BREAKDOWN_GROUPS.items():
        breakdowns[dimension] = {}
        for group_index, (label, count) in enumerate(groups):
            breakdowns[dimension][label] = {
                summary["approach"]: {
                    "top1_accuracy": (
                        0.28 + approach_index * 0.16 + (group_index % 3) * 0.02
                    ),
                    "total_bugs": count,
                }
                for approach_index, summary in enumerate(DEMO_SUMMARIES)
            }
    return breakdowns


DEMO_EVALUATION = {
    "summaries": DEMO_SUMMARIES,
    "breakdowns": _build_breakdowns(),
}
