from dataclasses import dataclass

from app.core.matching_config import MatchingConfig
from app.core.subject_taxonomy import display_term, normalize_subject, normalize_term
from app.models.recommendation import GuardDecision


@dataclass(frozen=True)
class GuardInput:
    similarity_score: float
    expected_subject: str | None
    expected_category: str | None
    required_tags: tuple[str, ...]
    image_subject: str
    image_subject_code: str
    image_category: str
    image_tags: tuple[str, ...]
    vision_confidence: float
    is_low_confidence: bool
    metadata_status: str
    metadata_valid: bool


@dataclass(frozen=True)
class GuardResult:
    decision: GuardDecision
    explanation: str


class MismatchGuard:
    """Pure, deterministic safety gate over existing metadata and similarity."""

    def __init__(self, config: MatchingConfig | None = None) -> None:
        self.config = config or MatchingConfig()

    def evaluate(self, candidate: GuardInput) -> GuardResult:
        if not candidate.metadata_valid:
            return GuardResult(
                GuardDecision.INVALID_METADATA,
                "Image metadata is invalid or unusable for deterministic matching.",
            )
        if (
            candidate.metadata_status != "trusted"
            or candidate.is_low_confidence
            or candidate.vision_confidence < self.config.minimum_vision_confidence
        ):
            if candidate.vision_confidence < self.config.minimum_vision_confidence:
                explanation = (
                    f"Image classification confidence {candidate.vision_confidence:.2f} "
                    "is below the configured minimum "
                    f"{self.config.minimum_vision_confidence:.2f}."
                )
            else:
                explanation = "Image metadata is flagged as low confidence."
            return GuardResult(
                GuardDecision.LOW_CONFIDENCE,
                explanation,
            )

        expected_subject = normalize_subject(candidate.expected_subject)
        image_subject = normalize_subject(candidate.image_subject_code) or normalize_subject(
            candidate.image_subject
        )
        if expected_subject and image_subject and expected_subject != image_subject:
            return GuardResult(
                GuardDecision.SUBJECT_MISMATCH,
                f"Expected {display_term(candidate.expected_subject)}, but the image was "
                f"classified as {display_term(candidate.image_subject)}.",
            )

        expected_category = normalize_term(candidate.expected_category)
        image_category = normalize_term(candidate.image_category)
        if expected_category and image_category and expected_category != image_category:
            return GuardResult(
                GuardDecision.CATEGORY_MISMATCH,
                f"Expected category {display_term(candidate.expected_category)}, but image "
                f"category is {display_term(candidate.image_category)}.",
            )

        normalized_tags = {normalize_term(tag) for tag in candidate.image_tags}
        missing = [
            tag
            for tag in candidate.required_tags
            if normalize_term(tag) not in normalized_tags
        ]
        if missing:
            return GuardResult(
                GuardDecision.REQUIRED_TAG_MISSING,
                "Image is missing required tag(s): "
                + ", ".join(display_term(tag) for tag in missing)
                + ".",
            )

        if candidate.similarity_score < self.config.minimum_similarity:
            return GuardResult(
                GuardDecision.LOW_SIMILARITY,
                f"Semantic similarity {candidate.similarity_score:.2f} is below the "
                f"configured minimum {self.config.minimum_similarity:.2f}.",
            )
        return GuardResult(
            GuardDecision.ACCEPTED,
            "Subject and category match with sufficient semantic similarity.",
        )
