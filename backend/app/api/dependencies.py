from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.processing_jobs import ProcessingJobRepository
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.posts import PostRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.providers.embedding import EmbeddingProvider, SentenceTransformerEmbeddingProvider
from app.providers.vision import GeminiVisionProvider, VisionProvider
from app.providers.fake import FakeVisionProvider
from app.services.image_analysis import ImageAnalysisService
from app.services.image_assets import ImageAssetService
from app.services.image_storage import LocalImageStorage
from app.services.processing_jobs import ProcessingJobService
from app.services.embeddings import EmbeddingService
from app.services.posts import PostService
from app.services.image_retrieval import ImageRetrievalService
from app.services.readiness import DatabaseReadinessService

DatabaseSession = Annotated[Session, Depends(get_db_session)]


def get_readiness_service(session: DatabaseSession) -> DatabaseReadinessService:
    return DatabaseReadinessService(session)


ReadinessService = Annotated[
    DatabaseReadinessService,
    Depends(get_readiness_service),
]


@lru_cache
def get_image_storage() -> LocalImageStorage:
    settings = get_settings()
    return LocalImageStorage(
        settings.image_storage_root,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )


def get_image_asset_service(
    session: DatabaseSession,
    storage: Annotated[LocalImageStorage, Depends(get_image_storage)],
) -> ImageAssetService:
    return ImageAssetService(ImageAssetRepository(session), storage)


ImageAssetsService = Annotated[
    ImageAssetService,
    Depends(get_image_asset_service),
]


@lru_cache
def get_vision_provider() -> VisionProvider:
    settings = get_settings()
    if settings.vision_provider == "fake":
        return FakeVisionProvider(
            {
                "subject": "red fox",
                "subject_code": "red_fox",
                "category": "animal",
                "caption": "A red fox in a deterministic worker fixture",
                "tags": ["red fox", "worker fixture"],
                "attributes": ["orange fur"],
                "objects": ["fox"],
                "confidence": 0.95,
            }
        )
    if settings.vision_provider != "gemini":
        raise RuntimeError("Unsupported VISION_PROVIDER configuration")
    return GeminiVisionProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_vision_model,
        timeout_seconds=settings.vision_timeout_seconds,
        estimated_cost_usd=settings.vision_estimated_cost_per_call_usd,
    )


def get_image_analysis_service(
    session: DatabaseSession,
    storage: Annotated[LocalImageStorage, Depends(get_image_storage)],
    provider: Annotated[VisionProvider, Depends(get_vision_provider)],
) -> ImageAnalysisService:
    settings = get_settings()
    return ImageAnalysisService(
        ImageAssetRepository(session),
        ImageMetadataRepository(session),
        storage,
        provider,
        low_confidence_threshold=settings.vision_low_confidence_threshold,
        vision_budget_usd=settings.vision_budget_usd,
    )


ImageAnalysis = Annotated[
    ImageAnalysisService,
    Depends(get_image_analysis_service),
]


def get_processing_job_service(session: DatabaseSession) -> ProcessingJobService:
    settings = get_settings()
    return ProcessingJobService(
        ProcessingJobRepository(session),
        ImageAssetRepository(session),
        max_attempts=settings.processing_max_attempts,
    )


ProcessingJobs = Annotated[
    ProcessingJobService,
    Depends(get_processing_job_service),
]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider != "local":
        raise RuntimeError("Unsupported EMBEDDING_PROVIDER configuration")
    return SentenceTransformerEmbeddingProvider(
        model=settings.embedding_model,
        version=settings.embedding_version,
        dimensions=settings.embedding_dimensions,
        normalize=settings.embedding_normalize,
    )


def get_embedding_service(
    session: DatabaseSession,
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> EmbeddingService:
    return EmbeddingService(
        EmbeddingRepository(session),
        ImageAssetRepository(session),
        ImageMetadataRepository(session),
        PostRepository(session),
        provider,
    )


Embeddings = Annotated[EmbeddingService, Depends(get_embedding_service)]


def get_post_service(session: DatabaseSession) -> PostService:
    return PostService(PostRepository(session))


Posts = Annotated[PostService, Depends(get_post_service)]


def get_image_retrieval_service(
    session: DatabaseSession,
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> ImageRetrievalService:
    return ImageRetrievalService(
        PostRepository(session),
        ImageRetrievalRepository(session),
        embedding_model=provider.model_name,
        embedding_version=provider.model_version,
        dimensions=provider.dimensions,
    )


ImageRetrieval = Annotated[
    ImageRetrievalService, Depends(get_image_retrieval_service)
]
