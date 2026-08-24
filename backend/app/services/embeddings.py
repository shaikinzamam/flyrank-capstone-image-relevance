from datetime import UTC, datetime
from hashlib import sha256
from math import isfinite
from time import perf_counter
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.models.embedding import EMBEDDING_DIMENSIONS, ImageEmbedding, PostEmbedding
from app.models.image_metadata import AiCallLog, MetadataStatus
from app.providers.embedding import EmbeddingProvider
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.posts import PostRepository
from app.schemas.image_metadata import VisionMetadata
from app.services.image_assets import ImageNotFoundError
from app.services.posts import PostNotFoundError
from app.services.semantic_text import (
    build_image_semantic_text,
    build_post_semantic_text,
)


class EmbeddingError(Exception):
    pass


class EmbeddingEligibilityError(EmbeddingError):
    pass


class EmbeddingProviderFailureError(EmbeddingError):
    pass


class EmbeddingValidationError(EmbeddingError):
    pass


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingPersistenceError(EmbeddingError):
    pass


class EmbeddingService:
    def __init__(
        self,
        embeddings: EmbeddingRepository,
        images: ImageAssetRepository,
        metadata: ImageMetadataRepository,
        posts: PostRepository,
        provider: EmbeddingProvider,
    ) -> None:
        self._embeddings = embeddings
        self._images = images
        self._metadata = metadata
        self._posts = posts
        self._provider = provider

    def image_is_low_confidence(self, image_id: UUID) -> bool | None:
        metadata = self._metadata.get_by_image_id(image_id)
        return metadata.is_low_confidence if metadata is not None else None

    def embed_image(self, image_id: UUID) -> tuple[ImageEmbedding, bool]:
        if self._images.get(image_id) is None:
            raise ImageNotFoundError("Image asset not found")
        metadata = self._metadata.get_by_image_id(image_id)
        if metadata is None:
            raise EmbeddingEligibilityError("Image metadata is missing")
        if metadata.metadata_status not in {
            MetadataStatus.TRUSTED.value,
            MetadataStatus.FLAGGED.value,
        }:
            raise EmbeddingEligibilityError("Image metadata is terminally invalid")
        try:
            VisionMetadata.model_validate(
                {
                    "subject": metadata.subject,
                    "subject_code": metadata.subject_code,
                    "category": metadata.category,
                    "caption": metadata.caption,
                    "tags": metadata.tags,
                    "attributes": metadata.attributes,
                    "objects": metadata.objects,
                    "confidence": metadata.confidence,
                }
            )
        except ValidationError as exc:
            raise EmbeddingEligibilityError("Image metadata is schema-invalid") from exc

        source_text = build_image_semantic_text(metadata)
        source_hash = self._source_hash(source_text)
        existing = self._embeddings.get_image(
            image_id, self._provider.model_name, self._provider.model_version
        )
        if existing is not None and existing.source_text_hash == source_hash:
            self._validate_stored_embedding(existing.dimensions)
            return existing, True

        vector, call_log = self._generate(source_text, image_id=image_id)
        if existing is None:
            embedding = ImageEmbedding(
                image_id=image_id,
                embedding_model=self._provider.model_name,
                embedding_version=self._provider.model_version,
                dimensions=EMBEDDING_DIMENSIONS,
                source_text_hash=source_hash,
                vector=vector,
            )
            self._embeddings.add(embedding)
        else:
            embedding = existing
            embedding.vector = vector
            embedding.dimensions = EMBEDDING_DIMENSIONS
            embedding.source_text_hash = source_hash
            embedding.updated_at = datetime.now(UTC)
        self._persist(embedding, call_log)
        return embedding, False

    def embed_post(self, post_id: UUID) -> tuple[PostEmbedding, bool]:
        post = self._posts.get(post_id)
        if post is None:
            raise PostNotFoundError("Post not found")
        source_text = build_post_semantic_text(post)
        source_hash = self._source_hash(source_text)
        existing = self._embeddings.get_post(
            post_id, self._provider.model_name, self._provider.model_version
        )
        if existing is not None and existing.source_text_hash == source_hash:
            self._validate_stored_embedding(existing.dimensions)
            return existing, True

        vector, call_log = self._generate(source_text, post_id=post_id)
        if existing is None:
            embedding = PostEmbedding(
                post_id=post_id,
                embedding_model=self._provider.model_name,
                embedding_version=self._provider.model_version,
                dimensions=EMBEDDING_DIMENSIONS,
                source_text_hash=source_hash,
                vector=vector,
            )
            self._embeddings.add(embedding)
        else:
            embedding = existing
            embedding.vector = vector
            embedding.dimensions = EMBEDDING_DIMENSIONS
            embedding.source_text_hash = source_hash
            embedding.updated_at = datetime.now(UTC)
        self._persist(embedding, call_log)
        return embedding, False

    def _generate(
        self,
        source_text: str,
        *,
        image_id: UUID | None = None,
        post_id: UUID | None = None,
    ) -> tuple[list[float], AiCallLog]:
        if self._provider.dimensions != EMBEDDING_DIMENSIONS:
            raise EmbeddingConfigurationError(
                "Embedding provider dimensions do not match the database schema"
            )
        call_log = AiCallLog(
            image_id=image_id,
            post_id=post_id,
            provider=self._provider.provider_name,
            model=self._provider.model_name,
            operation="embedding_generate",
            status="reserved",
            latency_ms=0,
            retry_count=0,
            estimated_cost_usd=self._provider.estimated_cost_usd,
        )
        self._embeddings.add(call_log)
        self._embeddings.commit()
        started = perf_counter()
        try:
            vector = self._provider.embed(source_text)
        except Exception as exc:
            self._finish_call(call_log, started, "failed", "provider_failure")
            self._embeddings.commit()
            raise EmbeddingProviderFailureError(
                "Embedding provider request failed"
            ) from exc
        try:
            self._validate_vector(vector)
        except EmbeddingValidationError:
            self._finish_call(call_log, started, "failed", "invalid_vector")
            self._embeddings.commit()
            raise
        self._finish_call(call_log, started, "succeeded", None)
        return [float(value) for value in vector], call_log

    def _persist(
        self, embedding: ImageEmbedding | PostEmbedding, call_log: AiCallLog
    ) -> None:
        try:
            self._embeddings.commit()
            self._embeddings.refresh(embedding)
        except SQLAlchemyError as exc:
            call_id = call_log.id
            self._embeddings.rollback()
            persisted_log = self._embeddings.get_call_log(call_id)
            if persisted_log is not None:
                persisted_log.status = "failed"
                persisted_log.error_code = "persistence_failure"
                self._embeddings.commit()
            raise EmbeddingPersistenceError(
                "Embedding database persistence failed"
            ) from exc

    @staticmethod
    def _source_hash(text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_stored_embedding(dimensions: int) -> None:
        if dimensions != EMBEDDING_DIMENSIONS:
            raise EmbeddingConfigurationError(
                "Stored embedding dimensions are incompatible"
            )

    @staticmethod
    def _validate_vector(vector: object) -> None:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise EmbeddingValidationError("Embedding vector must be non-empty")
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingValidationError(
                f"Embedding vector must contain {EMBEDDING_DIMENSIONS} values"
            )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            for value in vector
        ):
            raise EmbeddingValidationError(
                "Embedding vector must contain only finite numeric values"
            )

    @staticmethod
    def _finish_call(
        call_log: AiCallLog,
        started: float,
        status: str,
        error_code: str | None,
    ) -> None:
        call_log.status = status
        call_log.latency_ms = max(0, round((perf_counter() - started) * 1000))
        call_log.error_code = error_code
