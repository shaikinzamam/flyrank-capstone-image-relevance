from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.providers.vision import GeminiVisionProvider, VisionProvider
from app.services.image_analysis import ImageAnalysisService
from app.services.image_assets import ImageAssetService
from app.services.image_storage import LocalImageStorage
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
    if settings.vision_provider != "gemini":
        raise RuntimeError("Unsupported VISION_PROVIDER configuration")
    return GeminiVisionProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_vision_model,
        timeout_seconds=settings.vision_timeout_seconds,
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
    )


ImageAnalysis = Annotated[
    ImageAnalysisService,
    Depends(get_image_analysis_service),
]
