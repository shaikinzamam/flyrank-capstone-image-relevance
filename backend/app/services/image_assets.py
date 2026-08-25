from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.models.image_asset import ImageAsset, ProcessingStatus
from app.repositories.image_assets import ImageAssetRepository
from app.services.image_storage import LocalImageStorage, UnsupportedImageTypeError


class DuplicateImageError(Exception):
    pass


class ImageNotFoundError(Exception):
    pass


class InvalidFilenameError(Exception):
    pass


class ImageAssetService:
    def __init__(
        self,
        repository: ImageAssetRepository,
        storage: LocalImageStorage,
    ) -> None:
        self._repository = repository
        self._storage = storage

    async def create(self, upload: UploadFile) -> ImageAsset:
        filename = upload.filename or ""
        if not filename or len(filename) > 255 or "\x00" in filename:
            raise InvalidFilenameError(
                "A valid filename of at most 255 characters is required"
            )

        declared_mime_type = (
            (upload.content_type or "").lower().split(";", 1)[0].strip()
        )
        if declared_mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise UnsupportedImageTypeError(
                "Only JPEG, PNG, and WEBP images are supported"
            )

        staged = await self._storage.stage(upload)
        storage_key: str | None = None
        try:
            validated = self._storage.validate(staged, declared_mime_type)
            if self._repository.get_by_sha256(staged.sha256) is not None:
                raise DuplicateImageError(
                    "An image with identical content already exists"
                )

            storage_key = self._storage.promote(staged, validated)
            asset = ImageAsset(
                filename=filename,
                storage_key=storage_key,
                mime_type=validated.mime_type,
                byte_size=staged.byte_size,
                sha256=staged.sha256,
                processing_status=ProcessingStatus.UPLOADED.value,
            )
            self._repository.add(asset)
            try:
                self._repository.commit()
            except IntegrityError as exc:
                self._repository.rollback()
                self._storage.delete(storage_key)
                raise DuplicateImageError(
                    "An image with identical content already exists"
                ) from exc
            self._repository.refresh(asset)
            return asset
        except Exception:
            if storage_key is None:
                self._storage.discard(staged)
            else:
                self._storage.delete(storage_key)
            raise

    def list(self, *, offset: int, limit: int) -> list[ImageAsset]:
        return self._repository.list(offset=offset, limit=limit)

    def get(self, image_id: UUID) -> ImageAsset:
        asset = self._repository.get(image_id)
        if asset is None:
            raise ImageNotFoundError("Image asset not found")
        return asset

    def get_content_path(self, image_id: UUID) -> tuple[ImageAsset, Path]:
        asset = self.get(image_id)
        path = self._storage.get_validated_path(
            asset.storage_key,
            expected_mime_type=asset.mime_type,
            expected_sha256=asset.sha256,
            expected_byte_size=asset.byte_size,
        )
        return asset, path
