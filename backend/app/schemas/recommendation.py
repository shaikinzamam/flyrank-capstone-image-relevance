from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.recommendation import GuardDecision


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
