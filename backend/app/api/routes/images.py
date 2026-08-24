from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import ImageAnalysis, ImageAssetsService, ProcessingJobs
from app.schemas.image_asset import ImageAssetResponse
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
)
from app.services.processing_jobs import (
    IdempotencyConflictError,
    ProcessingImagesNotFoundError,
)
from app.api.routes.jobs import job_response

router = APIRouter(prefix="/images", tags=["images"])


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


@router.post(
    "/{image_id}/analyze",
    response_model=AnalyzeImageResponse,
    deprecated=True,
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
