import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.evaluations import EvaluationRepository
from app.services.evaluation import EvaluationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the labeled Phase 9 evaluation")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("artifacts/evaluation/latest.json"),
        help="Generated machine-readable report path",
    )
    args = parser.parse_args()
    settings = get_settings()
    with SessionLocal() as session:
        result = EvaluationService(
            EvaluationRepository(session), settings.evaluation_dataset_path
        ).run()
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Evaluation: {result.evaluator_version}")
    print(f"Dataset: {result.dataset_version}")
    print(f"Matching config: {result.config_version}")
    print(f"Examples: {result.total_examples}")
    print(f"Eligible recommendation examples: {result.eligible_recommendation_examples}")
    print(f"Correct top-1: {result.correct_top1}")
    print(f"Incorrect top-1: {result.incorrect_top1}")
    print(f"Correct refusals: {result.correct_no_confident_match}")
    print(f"Incorrect refusals: {result.incorrect_refusals}")
    print(f"Unsafe acceptances: {result.unsafe_acceptance_count}")
    print(f"Top-1 precision: {result.top1_precision:.4f}")
    print(f"JSON report: {args.json_output}")


if __name__ == "__main__":
    main()
