from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.image_asset import ImageAsset
from app.models.image_metadata import AiCallLog, ImageMetadata


class ImageMetadataRepository:
    def __init__(self, session: Session, workspace_id: UUID | None = None) -> None:
        self._session = session
        self.workspace_id = workspace_id

    def get_by_image_id(self, image_id: UUID) -> ImageMetadata | None:
        return self._session.scalar(
            select(ImageMetadata)
            .join(ImageAsset, ImageAsset.id == ImageMetadata.image_id)
            .where(
                ImageMetadata.image_id == image_id,
                *(() if self.workspace_id is None else (ImageAsset.workspace_id == self.workspace_id,)),
            )
        )

    def add(self, metadata: ImageMetadata) -> None:
        self._session.add(metadata)

    def add_call_log(self, call_log: AiCallLog) -> None:
        if self.workspace_id is not None:
            call_log.workspace_id = self.workspace_id
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
                select(func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0)).where(
                    *(() if self.workspace_id is None else (AiCallLog.workspace_id == self.workspace_id,))
                )
            )
            or 0.0
        )

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, metadata: ImageMetadata) -> None:
        self._session.refresh(metadata)
