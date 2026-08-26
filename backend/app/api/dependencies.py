from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.processing_jobs import ProcessingJobRepository
from app.repositories.embeddings import EmbeddingRepository
from app.repositories.posts import PostRepository
from app.repositories.image_retrieval import ImageRetrievalRepository
from app.repositories.recommendations import RecommendationRepository
from app.repositories.evaluations import EvaluationRepository
from app.repositories.auth import AuthRepository
from app.models.workspace import Workspace
from app.providers.embedding import EmbeddingProvider, SentenceTransformerEmbeddingProvider
from app.providers.corpus import (
    CorpusFixtureEmbeddingProvider,
    CorpusFixtureVisionProvider,
)
from app.providers.vision import GeminiVisionProvider, VisionProvider
from app.providers.fake import FakeVisionProvider
from app.services.image_analysis import ImageAnalysisService
from app.services.image_assets import ImageAssetService
from app.services.image_storage import LocalImageStorage
from app.services.processing_jobs import ProcessingJobService
from app.services.embeddings import EmbeddingService
from app.services.posts import PostService
from app.services.image_retrieval import ImageRetrievalService
from app.services.recommendations import RecommendationService
from app.services.recommendation_reviews import RecommendationReviewService
from app.services.evaluation import EvaluationService
from app.services.readiness import DatabaseReadinessService
from app.services.auth import AuthenticationService, InvalidApiCredentialError

DatabaseSession = Annotated[Session, Depends(get_db_session)]
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_workspace(
    session: DatabaseSession,
    credential: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> Workspace:
    if credential is None or credential.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer API credential required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return AuthenticationService(AuthRepository(session)).authenticate(
            credential.credentials
        )
    except InvalidApiCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API credential",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


AuthenticatedWorkspace = Annotated[Workspace, Depends(get_current_workspace)]


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
    workspace: AuthenticatedWorkspace,
    storage: Annotated[LocalImageStorage, Depends(get_image_storage)],
) -> ImageAssetService:
    return ImageAssetService(ImageAssetRepository(session, workspace.id), storage)


ImageAssetsService = Annotated[
    ImageAssetService,
    Depends(get_image_asset_service),
]


@lru_cache
def get_vision_provider() -> VisionProvider:
    settings = get_settings()
    if settings.vision_provider == "corpus_fixture":
        return CorpusFixtureVisionProvider(settings.corpus_manifest_path)
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
    workspace: AuthenticatedWorkspace,
    storage: Annotated[LocalImageStorage, Depends(get_image_storage)],
    provider: Annotated[VisionProvider, Depends(get_vision_provider)],
) -> ImageAnalysisService:
    settings = get_settings()
    return ImageAnalysisService(
        ImageAssetRepository(session, workspace.id),
        ImageMetadataRepository(session, workspace.id),
        storage,
        provider,
        low_confidence_threshold=settings.vision_low_confidence_threshold,
        vision_budget_usd=settings.vision_budget_usd,
    )


ImageAnalysis = Annotated[
    ImageAnalysisService,
    Depends(get_image_analysis_service),
]


def get_processing_job_service(
    session: DatabaseSession, workspace: AuthenticatedWorkspace
) -> ProcessingJobService:
    settings = get_settings()
    return ProcessingJobService(
        ProcessingJobRepository(session, workspace.id),
        ImageAssetRepository(session, workspace.id),
        PostRepository(session, workspace.id),
        max_attempts=settings.processing_max_attempts,
    )


ProcessingJobs = Annotated[
    ProcessingJobService,
    Depends(get_processing_job_service),
]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "corpus_fixture":
        return CorpusFixtureEmbeddingProvider()
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
    workspace: AuthenticatedWorkspace,
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> EmbeddingService:
    return EmbeddingService(
        EmbeddingRepository(session, workspace.id),
        ImageAssetRepository(session, workspace.id),
        ImageMetadataRepository(session, workspace.id),
        PostRepository(session, workspace.id),
        provider,
    )


Embeddings = Annotated[EmbeddingService, Depends(get_embedding_service)]


def get_post_service(
    session: DatabaseSession, workspace: AuthenticatedWorkspace
) -> PostService:
    return PostService(PostRepository(session, workspace.id))


Posts = Annotated[PostService, Depends(get_post_service)]


def get_image_retrieval_service(
    session: DatabaseSession,
    workspace: AuthenticatedWorkspace,
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> ImageRetrievalService:
    return ImageRetrievalService(
        PostRepository(session, workspace.id),
        ImageRetrievalRepository(session, workspace.id),
        embedding_model=provider.model_name,
        embedding_version=provider.model_version,
        dimensions=provider.dimensions,
    )


ImageRetrieval = Annotated[
    ImageRetrievalService, Depends(get_image_retrieval_service)
]


def get_recommendation_service(
    session: DatabaseSession,
    workspace: AuthenticatedWorkspace,
    retrieval: ImageRetrieval,
) -> RecommendationService:
    return RecommendationService(
        PostRepository(session, workspace.id),
        retrieval,
        RecommendationRepository(session, workspace.id),
    )


Recommendations = Annotated[
    RecommendationService, Depends(get_recommendation_service)
]


def get_recommendation_review_service(
    session: DatabaseSession,
    workspace: AuthenticatedWorkspace,
) -> RecommendationReviewService:
    return RecommendationReviewService(
        RecommendationRepository(session, workspace.id),
        PostRepository(session, workspace.id),
        ImageAssetRepository(session, workspace.id),
    )


RecommendationReviews = Annotated[
    RecommendationReviewService, Depends(get_recommendation_review_service)
]


def get_evaluation_service(
    session: DatabaseSession, workspace: AuthenticatedWorkspace
) -> EvaluationService:
    settings = get_settings()
    return EvaluationService(
        EvaluationRepository(session, workspace.id), settings.evaluation_dataset_path
    )


Evaluations = Annotated[EvaluationService, Depends(get_evaluation_service)]
