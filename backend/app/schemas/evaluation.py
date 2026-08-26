from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.recommendation import GuardDecision

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
FixtureId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$",
    ),
]


class EvaluationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_image_id: FixtureId
    subject: NonEmptyText
    subject_code: NonEmptyText
    category: NonEmptyText
    tags: Annotated[list[NonEmptyText], Field(min_length=1, max_length=20)]
    similarity_score: Annotated[float, Field(ge=-1, le=1)]
    vision_confidence: Annotated[float, Field(ge=0, le=1)]
    is_low_confidence: bool = False
    metadata_status: Literal["trusted", "flagged"] = "trusted"


class EvaluationExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: NonEmptyText
    example_id: FixtureId
    article_title: NonEmptyText
    article_body: NonEmptyText
    expected_subject: NonEmptyText | None
    expected_category: NonEmptyText | None
    required_tags: list[NonEmptyText]
    acceptable_image_ids: list[FixtureId]
    unsafe_image_ids: list[FixtureId]
    expect_no_confident_match: bool
    expected_guard_decisions: dict[FixtureId, GuardDecision]
    candidates: Annotated[list[EvaluationCandidate], Field(min_length=1, max_length=20)]
    notes: NonEmptyText

    @model_validator(mode="after")
    def validate_labels(self) -> "EvaluationExample":
        candidate_ids = [candidate.fixture_image_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate fixture_image_id values must be unique")
        candidate_set = set(candidate_ids)
        acceptable = set(self.acceptable_image_ids)
        unsafe = set(self.unsafe_image_ids)
        if acceptable & unsafe:
            raise ValueError("acceptable and unsafe image labels must be disjoint")
        if not (acceptable | unsafe) <= candidate_set:
            raise ValueError("all image labels must reference declared candidates")
        if (acceptable | unsafe) != candidate_set:
            raise ValueError("every candidate must be labeled acceptable or unsafe")
        if set(self.expected_guard_decisions) != candidate_set:
            raise ValueError("every candidate must have an explicit expected guard decision")
        if self.expect_no_confident_match and acceptable:
            raise ValueError("no-match examples cannot declare acceptable images")
        if not self.expect_no_confident_match and not acceptable:
            raise ValueError("recommendation examples require an acceptable image")
        return self


class CandidateEvaluationResult(BaseModel):
    fixture_image_id: str
    rank: int
    similarity_score: float
    decision: GuardDecision
    reason_code: GuardDecision
    explanation: str
    expected_decision: GuardDecision
    decision_correct: bool
    acceptable: bool
    unsafe: bool


class ExampleEvaluationResult(BaseModel):
    example_id: str
    expected_result: str
    actual_result: str
    selected_image_id: str | None
    correct: bool
    expected_subject: str | None
    expected_category: str | None
    candidates: list[CandidateEvaluationResult]


class CategoryEvaluationResult(BaseModel):
    examples: int
    correct_outcomes: int


class EvaluationReport(BaseModel):
    evaluator_version: str
    dataset_version: str
    config_version: str
    embedding_model: str
    embedding_version: str
    minimum_similarity: float
    minimum_vision_confidence: float
    total_examples: int
    eligible_recommendation_examples: int
    correct_top1: int
    incorrect_top1: int
    correct_no_confident_match: int
    incorrect_refusals: int
    unsafe_acceptance_count: int
    correct_safe_rejections: int
    top1_precision: float
    issued_recommendation_precision: float
    safe_acceptance_precision: float
    unsafe_rejection_recall: float
    per_category: dict[str, CategoryEvaluationResult]
    examples: list[ExampleEvaluationResult]


class EvaluationRunResponse(EvaluationReport):
    run_id: UUID
    created_at: datetime
