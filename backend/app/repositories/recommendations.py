from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation, RecommendationRun


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
