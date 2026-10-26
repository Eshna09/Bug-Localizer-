"""
CLI script to run a localization experiment over a bug dataset.

Usage:
    python scripts/run_experiment.py \
        --dataset /path/to/bug_dataset.json \
        --approaches keyword structural llm_only rag_llm \
        --top-k 5 \
        --output results.json

This script accesses ground truth ONLY for evaluation — never for localization.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.experiment_runner import ExperimentRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run bug localization experiment")
    parser.add_argument("--dataset", required=True, help="Path to bug dataset JSON")
    parser.add_argument(
        "--approaches",
        nargs="+",
        default=["keyword", "structural", "llm_only", "rag_llm"],
        choices=["keyword", "structural", "llm_only", "rag_llm"],
        help="Approaches to evaluate",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Top-K predictions")
    parser.add_argument("--output", default="experiment_results.json", help="Output file")
    args = parser.parse_args()

    if not Path(args.dataset).exists():
        logger.error("Dataset file not found: %s", args.dataset)
        sys.exit(1)

    runner = ExperimentRunner(top_k=args.top_k)
    logger.info("Starting experiment...")
    logger.info("Dataset: %s", args.dataset)
    logger.info("Approaches: %s", args.approaches)
    logger.info("Top-K: %d", args.top_k)

    results = runner.run(
        dataset_path=args.dataset,
        approaches=args.approaches,
    )

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info("Results written to: %s", output_path)

    # Print summary table
    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS")
    print("=" * 60)
    comparison = results.get("comparison", {}).get("ranked", [])
    for entry in comparison:
        print(
            f"#{entry['rank']} {entry['approach']:20s}  "
            f"Top-1: {entry['top1_accuracy']:.3f}  "
            f"Top-3: {entry['top3_accuracy']:.3f}  "
            f"Top-5: {entry['top5_accuracy']:.3f}  "
            f"MRR: {entry['mrr']:.3f}"
        )
    print("=" * 60)


if __name__ == "__main__":
    main()
