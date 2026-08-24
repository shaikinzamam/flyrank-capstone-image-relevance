from uuid import UUID

from sqlalchemy import select
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

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, metadata: ImageMetadata) -> None:
        self._session.refresh(metadata)
