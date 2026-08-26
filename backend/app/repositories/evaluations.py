from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationRun


class EvaluationRepository:
    def __init__(self, session: Session, workspace_id: UUID | None = None) -> None:
        self._session = session
        self.workspace_id = workspace_id

    def add(self, run: EvaluationRun) -> EvaluationRun:
        if self.workspace_id is not None:
            run.workspace_id = self.workspace_id
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def get(self, run_id: UUID) -> EvaluationRun | None:
        return self._session.scalar(
            select(EvaluationRun).where(
                EvaluationRun.id == run_id,
                *(() if self.workspace_id is None else (EvaluationRun.workspace_id == self.workspace_id,)),
            )
        )

    def latest(self) -> EvaluationRun | None:
        return self._session.scalar(
            select(EvaluationRun).order_by(
                EvaluationRun.created_at.desc(), EvaluationRun.id.desc()
            ).where(
                *(() if self.workspace_id is None else (EvaluationRun.workspace_id == self.workspace_id,))
            )
        )
