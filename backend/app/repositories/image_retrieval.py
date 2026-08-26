from dataclasses import dataclass
from math import sqrt
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.embedding import ImageEmbedding, PostEmbedding
from app.models.image_asset import ImageAsset
from app.models.image_metadata import ImageMetadata
from app.models.post import Post


@dataclass(frozen=True)
class RankedImageRecord:
    image_id: UUID
    cosine_distance: float
    subject: str
    subject_code: str
    category: str
    caption: str
    tags: list[str]
    attributes: list[str]
    objects: list[str]
    vision_confidence: float
    is_low_confidence: bool
    metadata_status: str


class ImageRetrievalRepository:
    def __init__(self, session: Session, workspace_id: UUID | None = None) -> None:
        self._session = session
        self.workspace_id = workspace_id

    def _post_scope(self):
        return () if self.workspace_id is None else (Post.workspace_id == self.workspace_id,)

    def _image_scope(self):
        return () if self.workspace_id is None else (ImageAsset.workspace_id == self.workspace_id,)

    def get_post_embedding(
        self,
        post_id: UUID,
        *,
        model: str,
        version: str,
        dimensions: int,
    ) -> PostEmbedding | None:
        return self._session.scalar(
            select(PostEmbedding).join(Post).where(
                PostEmbedding.post_id == post_id,
                PostEmbedding.embedding_model == model,
                PostEmbedding.embedding_version == version,
                PostEmbedding.dimensions == dimensions,
                *self._post_scope(),
            )
        )

    def count_post_embeddings(self, post_id: UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(PostEmbedding)
                .join(Post)
                .where(PostEmbedding.post_id == post_id, *self._post_scope())
            )
            or 0
        )

    def count_image_embeddings(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(ImageEmbedding)
                .join(ImageAsset)
                .where(*self._image_scope())
            )
            or 0
        )

    def count_compatible_image_embeddings(
        self, *, model: str, version: str, dimensions: int
    ) -> int:
        return int(
            self._session.scalar(
                select(func.count()).select_from(ImageEmbedding).where(
                    ImageEmbedding.embedding_model == model,
                    ImageEmbedding.embedding_version == version,
                    ImageEmbedding.dimensions == dimensions,
                ).join(ImageAsset).where(*self._image_scope())
            )
            or 0
        )

    def rank_images(
        self,
        post_vector: Any,
        *,
        model: str,
        version: str,
        dimensions: int,
        top_k: int,
    ) -> list[RankedImageRecord]:
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            return self._rank_postgresql(
                post_vector,
                model=model,
                version=version,
                dimensions=dimensions,
                top_k=top_k,
            )
        return self._rank_test_dialect(
            post_vector,
            model=model,
            version=version,
            dimensions=dimensions,
            top_k=top_k,
        )

    def _rank_postgresql(
        self,
        post_vector: Any,
        *,
        model: str,
        version: str,
        dimensions: int,
        top_k: int,
    ) -> list[RankedImageRecord]:
        distance = ImageEmbedding.vector.cosine_distance(post_vector).label(
            "cosine_distance"
        )
        statement = (
            select(ImageEmbedding.image_id, distance, ImageMetadata)
            .join(ImageMetadata, ImageMetadata.image_id == ImageEmbedding.image_id)
            .join(ImageAsset, ImageAsset.id == ImageEmbedding.image_id)
            .where(
                ImageEmbedding.embedding_model == model,
                ImageEmbedding.embedding_version == version,
                ImageEmbedding.dimensions == dimensions,
                distance.is_not(None),
                *self._image_scope(),
            )
            .order_by(distance.asc(), ImageEmbedding.image_id.asc())
            .limit(top_k)
        )
        return [
            self._record(image_id, float(cosine_distance), metadata)
            for image_id, cosine_distance, metadata in self._session.execute(statement)
        ]

    def _rank_test_dialect(
        self,
        post_vector: Any,
        *,
        model: str,
        version: str,
        dimensions: int,
        top_k: int,
    ) -> list[RankedImageRecord]:
        """SQLite-only deterministic fallback; production ranking stays in pgvector."""
        rows = self._session.execute(
            select(ImageEmbedding, ImageMetadata)
            .join(ImageMetadata, ImageMetadata.image_id == ImageEmbedding.image_id)
            .join(ImageAsset, ImageAsset.id == ImageEmbedding.image_id)
            .where(
                ImageEmbedding.embedding_model == model,
                ImageEmbedding.embedding_version == version,
                ImageEmbedding.dimensions == dimensions,
                *self._image_scope(),
            )
        )
        ranked: list[RankedImageRecord] = []
        for embedding, metadata in rows:
            distance = self._cosine_distance(post_vector, embedding.vector)
            if distance is not None:
                ranked.append(self._record(embedding.image_id, distance, metadata))
        ranked.sort(key=lambda item: (item.cosine_distance, str(item.image_id)))
        return ranked[:top_k]

    @staticmethod
    def _cosine_distance(left: Any, right: Any) -> float | None:
        left_values = [float(value) for value in left]
        right_values = [float(value) for value in right]
        left_norm = sqrt(sum(value * value for value in left_values))
        right_norm = sqrt(sum(value * value for value in right_values))
        if left_norm == 0 or right_norm == 0:
            return None
        similarity = sum(
            left_value * right_value
            for left_value, right_value in zip(left_values, right_values, strict=True)
        ) / (left_norm * right_norm)
        return 1.0 - similarity

    @staticmethod
    def _record(
        image_id: UUID, cosine_distance: float, metadata: ImageMetadata
    ) -> RankedImageRecord:
        return RankedImageRecord(
            image_id=image_id,
            cosine_distance=cosine_distance,
            subject=metadata.subject,
            subject_code=metadata.subject_code,
            category=metadata.category,
            caption=metadata.caption,
            tags=metadata.tags,
            attributes=metadata.attributes,
            objects=metadata.objects,
            vision_confidence=metadata.confidence,
            is_low_confidence=metadata.is_low_confidence,
            metadata_status=metadata.metadata_status,
        )
