import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.evaluation import EvaluationExample, EvaluationReport
from app.services.evaluation import (
    EvaluationDatasetError,
    EvaluationEngine,
    load_evaluation_dataset,
)

DATASET_PATH = get_settings().evaluation_dataset_path


@pytest.fixture(scope="module")
def dataset() -> tuple[str, list[EvaluationExample]]:
    return load_evaluation_dataset(DATASET_PATH)


@pytest.fixture(scope="module")
def baseline(
    dataset: tuple[str, list[EvaluationExample]],
) -> EvaluationReport:
    version, examples = dataset
    return EvaluationEngine().evaluate(version, examples)


def rebuild(example: EvaluationExample, **updates: object) -> EvaluationExample:
    values = example.model_dump(mode="json")
    values.update(updates)
    return EvaluationExample.model_validate(values)


def test_dataset_parses_with_unique_explicit_labels(
    dataset: tuple[str, list[EvaluationExample]],
) -> None:
    version, examples = dataset

    assert version == "evaluation-v1"
    assert len(examples) == 10
    assert len({example.example_id for example in examples}) == 10
    assert all(
        set(example.expected_guard_decisions)
        == {candidate.fixture_image_id for candidate in example.candidates}
        for example in examples
    )


def test_duplicate_ids_and_malformed_labels_are_rejected(tmp_path: Path) -> None:
    valid_line = DATASET_PATH.read_text(encoding="utf-8").splitlines()[0]
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(f"{valid_line}\n{valid_line}\n", encoding="utf-8")
    malformed = json.loads(valid_line)
    malformed["acceptable_image_ids"] = ["missing_fixture"]

    with pytest.raises(EvaluationDatasetError, match="Duplicate"):
        load_evaluation_dataset(duplicate)
    with pytest.raises(ValidationError, match="declared candidates"):
        EvaluationExample.model_validate(malformed)


def test_baseline_metrics_and_precision_formula_are_exact(
    baseline: EvaluationReport,
) -> None:
    assert baseline.total_examples == 10
    assert baseline.eligible_recommendation_examples == 3
    assert baseline.correct_top1 == 3
    assert baseline.incorrect_top1 == 0
    assert baseline.correct_no_confident_match == 7
    assert baseline.incorrect_refusals == 0
    assert baseline.unsafe_acceptance_count == 0
    assert baseline.correct_safe_rejections == 10
    assert baseline.top1_precision == 3 / (3 + 0)
    assert baseline.safe_acceptance_precision == 1.0
    assert baseline.unsafe_rejection_recall == 1.0
    assert baseline.config_version == "phase8-v1"
    assert baseline.evaluator_version == "phase9-v1"
    assert baseline.minimum_similarity == 0.70
    assert baseline.minimum_vision_confidence == 0.70
    assert baseline.embedding_model == "deterministic-evaluation-vectors"
    assert baseline.per_category["animal"].model_dump() == {
        "examples": 8,
        "correct_outcomes": 8,
    }


def test_incorrect_top1_and_unsafe_acceptance_are_counted(
    dataset: tuple[str, list[EvaluationExample]],
) -> None:
    _, examples = dataset
    direct = next(item for item in examples if item.example_id == "eval_red_fox_direct")
    relabeled = rebuild(
        direct,
        example_id="eval_red_fox_incorrect_label_metric_test",
        acceptable_image_ids=["wolf_related"],
        unsafe_image_ids=["fox_direct"],
    )

    report = EvaluationEngine().evaluate("metric-test", [direct, relabeled])

    assert report.correct_top1 == 1
    assert report.incorrect_top1 == 1
    assert report.unsafe_acceptance_count == 1
    assert report.top1_precision == 1 / (1 + 1)


def test_incorrect_refusal_and_correct_no_match_are_counted(
    dataset: tuple[str, list[EvaluationExample]],
) -> None:
    _, examples = dataset
    forced = next(
        item for item in examples if item.example_id == "eval_forced_wolf_on_fox"
    )
    expected_match = rebuild(
        forced,
        example_id="eval_forced_wolf_expected_match",
        expect_no_confident_match=False,
        acceptable_image_ids=["forced_wolf"],
        unsafe_image_ids=[],
    )

    report = EvaluationEngine().evaluate(
        "metric-test", [forced, expected_match]
    )

    assert report.correct_no_confident_match == 1
    assert report.incorrect_refusals == 1


def test_alias_and_fox_wolf_examples_capture_actual_guard_evidence(
    baseline: EvaluationReport,
) -> None:
    by_id = {example.example_id: example for example in baseline.examples}
    alias = by_id["eval_vulpes_vulpes_alias"]
    direct = by_id["eval_red_fox_direct"]

    assert alias.selected_image_id == "fox_alias"
    assert alias.correct is True
    assert direct.selected_image_id == "fox_direct"
    assert [(item.fixture_image_id, item.decision.value) for item in direct.candidates] == [
        ("wolf_related", "SUBJECT_MISMATCH"),
        ("fox_direct", "ACCEPTED"),
    ]


def test_repeated_runs_have_identical_metrics_and_evidence(
    dataset: tuple[str, list[EvaluationExample]], baseline: EvaluationReport
) -> None:
    version, examples = dataset
    repeated = EvaluationEngine().evaluate(version, examples)

    assert repeated.model_dump() == baseline.model_dump()
