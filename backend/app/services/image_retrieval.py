from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from pydantic import ValidationError

from app.models.embedding import EMBEDDING_DIMENSIONS
from app.repositories.image_retrieval import (
    ImageRetrievalRepository,
    RankedImageRecord,
)
from app.repositories.posts import PostRepository
from app.schemas.image_metadata import VisionMetadata
from app.schemas.retrieval import ImageCandidateResponse
from app.services.posts import PostNotFoundError


class RetrievalError(Exception):
    pass


class MissingPostEmbeddingError(RetrievalError):
    pass


class IncompatibleEmbeddingError(RetrievalError):
    pass


class InvalidSimilarityError(RetrievalError):
    pass


@dataclass(frozen=True)
class ImageRetrievalResult:
    post_id: UUID
    embedding_model: str
    embedding_version: str
    dimensions: int
    candidates: list[ImageCandidateResponse]


class ImageRetrievalService:
    def __init__(
        self,
        posts: PostRepository,
        retrieval: ImageRetrievalRepository,
        *,
        embedding_model: str,
        embedding_version: str,
        dimensions: int,
    ) -> None:
        self._posts = posts
        self._retrieval = retrieval
        self._model = embedding_model
        self._version = embedding_version
        self._dimensions = dimensions

    def retrieve(self, post_id: UUID, *, top_k: int) -> ImageRetrievalResult:
        if self._posts.get(post_id) is None:
            raise PostNotFoundError("Post not found")
        if self._dimensions != EMBEDDING_DIMENSIONS:
            raise IncompatibleEmbeddingError(
                "Configured retrieval dimensions do not match the vector schema"
            )
        post_embedding = self._retrieval.get_post_embedding(
            post_id,
            model=self._model,
            version=self._version,
            dimensions=self._dimensions,
        )
        if post_embedding is None:
            if self._retrieval.count_post_embeddings(post_id) > 0:
                raise IncompatibleEmbeddingError(
                    "Post embedding is incompatible with the configured retrieval model"
                )
            raise MissingPostEmbeddingError(
                "Post must be embedded before image retrieval"
            )

        total_images = self._retrieval.count_image_embeddings()
        compatible_images = self._retrieval.count_compatible_image_embeddings(
            model=self._model,
            version=self._version,
            dimensions=self._dimensions,
        )
        if total_images > 0 and compatible_images == 0:
            raise IncompatibleEmbeddingError(
                "No image embeddings are compatible with the post embedding"
            )
        records = self._retrieval.rank_images(
            post_embedding.vector,
            model=self._model,
            version=self._version,
            dimensions=self._dimensions,
            top_k=top_k,
        )
        candidates = self._valid_candidates(records)
        return ImageRetrievalResult(
            post_id=post_id,
            embedding_model=self._model,
            embedding_version=self._version,
            dimensions=self._dimensions,
            candidates=candidates,
        )

    @staticmethod
    def _valid_candidates(
        records: list[RankedImageRecord],
    ) -> list[ImageCandidateResponse]:
        candidates: list[ImageCandidateResponse] = []
        for record in records:
            try:
                VisionMetadata.model_validate(
                    {
                        "subject": record.subject,
                        "subject_code": record.subject_code,
                        "category": record.category,
                        "caption": record.caption,
                        "tags": record.tags,
                        "attributes": record.attributes,
                        "objects": record.objects,
                        "confidence": record.vision_confidence,
                    }
                )
            except ValidationError:
                continue
            similarity = 1.0 - record.cosine_distance
            if not isfinite(similarity):
                raise InvalidSimilarityError(
                    "Vector search returned a non-finite similarity"
                )
            similarity = min(1.0, max(-1.0, similarity))
            candidates.append(
                ImageCandidateResponse(
                    rank=len(candidates) + 1,
                    image_id=record.image_id,
                    similarity_score=similarity,
                    subject=record.subject,
                    category=record.category,
                    caption=record.caption,
                    tags=record.tags,
                    vision_confidence=record.vision_confidence,
                    is_low_confidence=record.is_low_confidence,
                )
            )
        return candidates
