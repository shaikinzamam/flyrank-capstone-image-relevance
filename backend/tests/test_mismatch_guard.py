import pytest

from app.core.matching_config import MatchingConfig
from app.models.recommendation import GuardDecision
from app.services.mismatch_guard import GuardInput, MismatchGuard


def candidate(**overrides: object) -> GuardInput:
    values: dict[str, object] = {
        "similarity_score": 0.90,
        "expected_subject": "red_fox",
        "expected_category": "animal",
        "required_tags": (),
        "image_subject": "red fox",
        "image_subject_code": "red_fox",
        "image_category": "animal",
        "image_tags": ("red fox", "snow", "winter"),
        "vision_confidence": 0.95,
        "is_low_confidence": False,
        "metadata_status": "trusted",
        "metadata_valid": True,
    }
    values.update(overrides)
    return GuardInput(**values)  # type: ignore[arg-type]


def test_correct_subject_and_scientific_alias_are_accepted() -> None:
    guard = MismatchGuard()

    direct = guard.evaluate(candidate())
    alias = guard.evaluate(candidate(expected_subject="Vulpes vulpes"))

    assert direct.decision == GuardDecision.ACCEPTED
    assert alias.decision == GuardDecision.ACCEPTED
    assert "sufficient semantic similarity" in alias.explanation


@pytest.mark.parametrize(
    ("overrides", "decision", "explanation_fragment"),
    [
        ({"metadata_valid": False}, GuardDecision.INVALID_METADATA, "invalid"),
        (
            {"vision_confidence": 0.69},
            GuardDecision.LOW_CONFIDENCE,
            "configured minimum 0.70",
        ),
        (
            {"is_low_confidence": True},
            GuardDecision.LOW_CONFIDENCE,
            "flagged",
        ),
        (
            {"image_subject": "gray wolf", "image_subject_code": "gray_wolf"},
            GuardDecision.SUBJECT_MISMATCH,
            "Expected red fox",
        ),
        (
            {
                "expected_subject": None,
                "expected_category": "wildlife",
                "image_category": "food",
            },
            GuardDecision.CATEGORY_MISMATCH,
            "wildlife",
        ),
        (
            {"required_tags": ("snow",), "image_tags": ("forest", "summer")},
            GuardDecision.REQUIRED_TAG_MISSING,
            "snow",
        ),
        (
            {"similarity_score": 0.69},
            GuardDecision.LOW_SIMILARITY,
            "configured minimum 0.70",
        ),
    ],
)
def test_guard_rejections_are_stable_and_readable(
    overrides: dict[str, object],
    decision: GuardDecision,
    explanation_fragment: str,
) -> None:
    result = MismatchGuard().evaluate(candidate(**overrides))

    assert result.decision == decision
    assert explanation_fragment in result.explanation


def test_guard_decision_order_prefers_invalid_confidence_subject_and_category() -> None:
    guard = MismatchGuard(MatchingConfig())

    invalid = guard.evaluate(
        candidate(
            metadata_valid=False,
            vision_confidence=0.1,
            image_subject_code="gray_wolf",
            image_subject="gray wolf",
            image_category="food",
            similarity_score=0.1,
        )
    )
    low_confidence = guard.evaluate(
        candidate(
            vision_confidence=0.1,
            image_subject_code="gray_wolf",
            image_subject="gray wolf",
            image_category="food",
            similarity_score=0.1,
        )
    )
    subject = guard.evaluate(
        candidate(
            image_subject_code="gray_wolf",
            image_subject="gray wolf",
            image_category="food",
            similarity_score=0.1,
        )
    )

    assert invalid.decision == GuardDecision.INVALID_METADATA
    assert low_confidence.decision == GuardDecision.LOW_CONFIDENCE
    assert subject.decision == GuardDecision.SUBJECT_MISMATCH
