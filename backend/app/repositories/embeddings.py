from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.embedding import ImageEmbedding, PostEmbedding
from app.models.image_metadata import AiCallLog


class EmbeddingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_image(
        self, image_id: UUID, model: str, version: str
    ) -> ImageEmbedding | None:
        return self._session.scalar(
            select(ImageEmbedding).where(
                ImageEmbedding.image_id == image_id,
                ImageEmbedding.embedding_model == model,
                ImageEmbedding.embedding_version == version,
            )
        )

    def get_post(
        self, post_id: UUID, model: str, version: str
    ) -> PostEmbedding | None:
        return self._session.scalar(
            select(PostEmbedding).where(
                PostEmbedding.post_id == post_id,
                PostEmbedding.embedding_model == model,
                PostEmbedding.embedding_version == version,
            )
        )

    def add(self, value: ImageEmbedding | PostEmbedding | AiCallLog) -> None:
        self._session.add(value)

    def get_call_log(self, call_id: UUID) -> AiCallLog | None:
        return self._session.get(AiCallLog, call_id)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, value: ImageEmbedding | PostEmbedding) -> None:
        self._session.refresh(value)
