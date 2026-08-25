from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.recommendation import (
    Recommendation,
    RecommendationReview,
    RecommendationRun,
)


class RecommendationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def persist(
        self, run: RecommendationRun, decisions: list[Recommendation]
    ) -> RecommendationRun:
        run.recommendations.extend(decisions)
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def get(self, recommendation_id: UUID) -> Recommendation | None:
        return self._session.scalar(
            select(Recommendation)
            .options(selectinload(Recommendation.reviews))
            .where(Recommendation.id == recommendation_id)
        )

    def add_review(
        self, recommendation: Recommendation, review: RecommendationReview
    ) -> RecommendationReview:
        recommendation.reviews.append(review)
        self._session.add(review)
        self._session.commit()
        self._session.refresh(review)
        return review
