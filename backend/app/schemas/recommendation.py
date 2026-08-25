from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.recommendation import GuardDecision, HumanReviewDecision
from app.schemas.image_asset import ImageAssetResponse
from app.schemas.post import PostResponse


class CandidateDecisionResponse(BaseModel):
    image_id: UUID
    rank: Annotated[int, Field(ge=1)]
    similarity_score: Annotated[float, Field(ge=-1, le=1)]
    vision_confidence: Annotated[float, Field(ge=0, le=1)]
    decision: GuardDecision
    reason_code: GuardDecision
    explanation: str


class RecommendationResponse(BaseModel):
    run_id: UUID
    post_id: UUID
    status: Literal["matched", "no_confident_match"]
    matching_config_version: str
    embedding_model: str
    embedding_version: str
    recommendation: CandidateDecisionResponse | None
    reason_code: Literal["NO_CONFIDENT_MATCH"] | None = None
    rejected_candidates: list[CandidateDecisionResponse]
    created_at: datetime


ReviewComment = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class RecommendationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: ReviewComment | None = None


class RecommendationReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recommendation_id: UUID
    decision: HumanReviewDecision
    comment: str | None
    reviewer_id: UUID | None
    created_at: datetime


class RecommendationDetailResponse(BaseModel):
    id: UUID
    run_id: UUID
    post: PostResponse
    candidate_image: ImageAssetResponse
    rank: Annotated[int, Field(ge=1)]
    similarity_score: Annotated[float, Field(ge=-1, le=1)]
    image_subject: str
    image_subject_code: str
    image_category: str
    image_tags: list[str]
    expected_subject: str | None
    expected_category: str | None
    required_tags: list[str]
    vision_confidence: Annotated[float, Field(ge=0, le=1)]
    metadata_valid: bool
    is_low_confidence: bool
    guard_decision: GuardDecision
    guard_reason_code: GuardDecision
    explanation: str
    human_review_permitted: bool
    human_review_state: Literal["pending", "approved", "rejected"]
    current_review: RecommendationReviewResponse | None
    created_at: datetime
