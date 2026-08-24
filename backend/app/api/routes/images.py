from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import ImageAssetsService
from app.schemas.image_asset import ImageAssetResponse
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

router = APIRouter(prefix="/images", tags=["images"])


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
