from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.embedding import ImageEmbedding, PostEmbedding
from app.models.image_asset import ImageAsset
from app.models.image_metadata import AiCallLog
from app.models.post import Post


class EmbeddingRepository:
    def __init__(self, session: Session, workspace_id: UUID | None = None) -> None:
        self._session = session
        self.workspace_id = workspace_id

    def get_image(
        self, image_id: UUID, model: str, version: str
    ) -> ImageEmbedding | None:
        return self._session.scalar(
            select(ImageEmbedding).join(ImageAsset).where(
                ImageEmbedding.image_id == image_id,
                ImageEmbedding.embedding_model == model,
                ImageEmbedding.embedding_version == version,
                *(() if self.workspace_id is None else (ImageAsset.workspace_id == self.workspace_id,)),
            )
        )

    def get_post(
        self, post_id: UUID, model: str, version: str
    ) -> PostEmbedding | None:
        return self._session.scalar(
            select(PostEmbedding).join(Post).where(
                PostEmbedding.post_id == post_id,
                PostEmbedding.embedding_model == model,
                PostEmbedding.embedding_version == version,
                *(() if self.workspace_id is None else (Post.workspace_id == self.workspace_id,)),
            )
        )

    def add(self, value: ImageEmbedding | PostEmbedding | AiCallLog) -> None:
        if isinstance(value, AiCallLog) and self.workspace_id is not None:
            value.workspace_id = self.workspace_id
        self._session.add(value)

    def get_call_log(self, call_id: UUID) -> AiCallLog | None:
        return self._session.scalar(
            select(AiCallLog).where(
                AiCallLog.id == call_id,
                *(() if self.workspace_id is None else (AiCallLog.workspace_id == self.workspace_id,)),
            )
        )

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, value: ImageEmbedding | PostEmbedding) -> None:
        self._session.refresh(value)
