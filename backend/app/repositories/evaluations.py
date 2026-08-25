from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationRun


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: EvaluationRun) -> EvaluationRun:
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def get(self, run_id: UUID) -> EvaluationRun | None:
        return self._session.get(EvaluationRun, run_id)

    def latest(self) -> EvaluationRun | None:
        return self._session.scalar(
            select(EvaluationRun).order_by(
                EvaluationRun.created_at.desc(), EvaluationRun.id.desc()
            )
        )
