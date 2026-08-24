from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.image_metadata import AiCallLog, ImageMetadata


class ImageMetadataRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_image_id(self, image_id: UUID) -> ImageMetadata | None:
        return self._session.scalar(
            select(ImageMetadata).where(ImageMetadata.image_id == image_id)
        )

    def add(self, metadata: ImageMetadata) -> None:
        self._session.add(metadata)

    def add_call_log(self, call_log: AiCallLog) -> None:
        self._session.add(call_log)

    def reserve_budget_lock(self) -> None:
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            self._session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": 7_319_405_101},
            )

    def total_estimated_cost(self) -> float:
        return float(
            self._session.scalar(
                select(func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0))
            )
            or 0.0
        )

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, metadata: ImageMetadata) -> None:
        self._session.refresh(metadata)
