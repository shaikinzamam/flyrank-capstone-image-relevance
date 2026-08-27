from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import (
    Embeddings,
    ImageAnalysis,
    ImageAssetsService,
    ProcessingJobs,
    require_development_environment,
)
from app.schemas.embedding import EmbeddingResponse
from app.schemas.image_asset import (
    ImageAssetResponse,
    ImageDetailResponse,
    ImageEmbeddingSummary,
)
from app.schemas.image_metadata import AnalyzeImageResponse, ImageMetadataResponse
from app.schemas.processing_job import (
    CreateProcessingJobRequest,
    ProcessingJobResponse,
)
from app.services.image_analysis import (
    ImageStateError,
    MalformedProviderResponseError,
    MetadataValidationError,
    VisionBudgetExceededError,
    VisionProviderConfigurationError,
    VisionProviderFailureError,
    VisionProviderTimeoutError,
)
from app.services.image_assets import (
    DuplicateImageError,
    ImageNotFoundError,
    InvalidFilenameError,
)
from app.services.image_storage import (
    ImageTooLargeError,
    InvalidImageError,
    UnsupportedImageTypeError,
    InvalidStoredImageError,
)
from app.services.processing_jobs import (
    IdempotencyConflictError,
    ProcessingImagesNotFoundError,
)
from app.services.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingEligibilityError,
    EmbeddingPersistenceError,
    EmbeddingProviderFailureError,
    EmbeddingValidationError,
)
from app.api.routes.jobs import job_response

router = APIRouter(prefix="/images", tags=["images"])


@router.post(
    "/{image_id}/embedding/debug-sync",
    response_model=EmbeddingResponse,
    deprecated=True,
    dependencies=[Depends(require_development_environment)],
)
def create_image_embedding_debug(
    image_id: UUID, service: Embeddings
) -> EmbeddingResponse:
    """Development-only diagnostic; production image embeddings run in jobs."""
    try:
        embedding, reused = service.embed_image(image_id)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EmbeddingEligibilityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (EmbeddingProviderFailureError, EmbeddingPersistenceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EmbeddingValidationError, EmbeddingConfigurationError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmbeddingResponse(
        id=embedding.id,
        resource_id=embedding.image_id,
        resource_type="image",
        embedding_model=embedding.embedding_model,
        embedding_version=embedding.embedding_version,
        dimensions=embedding.dimensions,
        source_text_hash=embedding.source_text_hash,
        reused=reused,
        is_low_confidence=service.image_is_low_confidence(image_id),
        created_at=embedding.created_at,
        updated_at=embedding.updated_at,
    )


@router.post(
    "/process",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_processing_job(
    request: CreateProcessingJobRequest,
    service: ProcessingJobs,
) -> ProcessingJobResponse:
    try:
        job, reused = service.create(
            request.image_ids,
            idempotency_key=request.idempotency_key,
        )
    except ProcessingImagesNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return job_response(job, reused=reused)


@router.post("", response_model=ImageAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    service: ImageAssetsService,
    file: UploadFile = File(...),
) -> ImageAssetResponse:
    try:
        asset = await service.create(file)
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except UnsupportedImageTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (InvalidImageError, InvalidFilenameError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except DuplicateImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()
    return ImageAssetResponse.model_validate(asset)


@router.get("", response_model=list[ImageAssetResponse])
def list_images(
    service: ImageAssetsService,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ImageAssetResponse]:
    return [
        ImageAssetResponse.model_validate(asset)
        for asset in service.list(offset=offset, limit=limit)
    ]


@router.get("/{image_id}", response_model=ImageAssetResponse)
def get_image(image_id: UUID, service: ImageAssetsService) -> ImageAssetResponse:
    try:
        asset = service.get(image_id)
    except ImageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ImageAssetResponse.model_validate(asset)


@router.get("/{image_id}/details", response_model=ImageDetailResponse)
def get_image_details(
    image_id: UUID, service: ImageAssetsService
) -> ImageDetailResponse:
    try:
        asset = service.get(image_id)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ImageDetailResponse(
        asset=ImageAssetResponse.model_validate(asset),
        metadata=(
            ImageMetadataResponse.model_validate(asset.metadata_record)
            if asset.metadata_record is not None
            else None
        ),
        embeddings=[
            ImageEmbeddingSummary.model_validate(embedding)
            for embedding in asset.embeddings
        ],
    )


@router.get("/{image_id}/content", response_class=FileResponse)
def get_image_content(image_id: UUID, service: ImageAssetsService) -> FileResponse:
    try:
        asset, path = service.get_content_path(image_id)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStoredImageError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{image_id}/analyze",
    response_model=AnalyzeImageResponse,
    deprecated=True,
    dependencies=[Depends(require_development_environment)],
)
def analyze_image(
    image_id: UUID,
    service: ImageAnalysis,
    reprocess: bool = Query(default=False),
) -> AnalyzeImageResponse:
    try:
        metadata, reused = service.analyze(image_id, reprocess=reprocess)
    except ImageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ImageStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except VisionProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except VisionProviderFailureError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VisionProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VisionBudgetExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except (MalformedProviderResponseError, MetadataValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return AnalyzeImageResponse(
        image_id=image_id,
        processing_status="processed",
        reused=reused,
        metadata=ImageMetadataResponse.model_validate(metadata),
    )
