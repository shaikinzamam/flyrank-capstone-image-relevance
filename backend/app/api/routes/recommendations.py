from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.dependencies import RecommendationReviews
from app.models.recommendation import HumanReviewDecision
from app.schemas.recommendation import (
    RecommendationDetailResponse,
    RecommendationReviewRequest,
    RecommendationReviewResponse,
)
from app.services.recommendation_reviews import (
    RecommendationNotFoundError,
    RecommendationReviewNotPermittedError,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/{recommendation_id}", response_model=RecommendationDetailResponse)
def get_recommendation(
    recommendation_id: UUID, service: RecommendationReviews
) -> RecommendationDetailResponse:
    try:
        return service.get_detail(recommendation_id)
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{recommendation_id}/reviews",
    response_model=list[RecommendationReviewResponse],
)
def list_recommendation_reviews(
    recommendation_id: UUID, service: RecommendationReviews
) -> list[RecommendationReviewResponse]:
    try:
        return service.list_reviews(recommendation_id)
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _review(
    recommendation_id: UUID,
    request: RecommendationReviewRequest,
    service: RecommendationReviews,
    decision: HumanReviewDecision,
) -> RecommendationReviewResponse:
    try:
        return service.review(
            recommendation_id,
            decision,
            comment=request.comment,
        )
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecommendationReviewNotPermittedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{recommendation_id}/approve",
    response_model=RecommendationReviewResponse,
)
def approve_recommendation(
    recommendation_id: UUID,
    service: RecommendationReviews,
    request: RecommendationReviewRequest | None = None,
) -> RecommendationReviewResponse:
    return _review(
        recommendation_id,
        request or RecommendationReviewRequest(),
        service,
        HumanReviewDecision.APPROVED,
    )


@router.post(
    "/{recommendation_id}/reject",
    response_model=RecommendationReviewResponse,
)
def reject_recommendation(
    recommendation_id: UUID,
    service: RecommendationReviews,
    request: RecommendationReviewRequest | None = None,
) -> RecommendationReviewResponse:
    return _review(
        recommendation_id,
        request or RecommendationReviewRequest(),
        service,
        HumanReviewDecision.REJECTED,
    )
