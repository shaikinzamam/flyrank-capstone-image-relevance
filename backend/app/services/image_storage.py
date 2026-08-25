from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from uuid import uuid4
import warnings

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": ("JPEG", ".jpg"),
    "image/png": ("PNG", ".png"),
    "image/webp": ("WEBP", ".webp"),
}
FORMAT_TO_MIME = {
    image_format: mime_type
    for mime_type, (image_format, _) in SUPPORTED_IMAGE_TYPES.items()
}


class ImageStorageError(Exception):
    """Base error for safe, client-facing upload failures."""


class UnsupportedImageTypeError(ImageStorageError):
    pass


class InvalidImageError(ImageStorageError):
    pass


class ImageTooLargeError(ImageStorageError):
    pass


class InvalidStoredImageError(ImageStorageError):
    pass


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class ValidatedImage:
    mime_type: str
    image_format: str


class LocalImageStorage:
    def __init__(
        self,
        root: Path,
        *,
        max_upload_bytes: int,
        max_image_pixels: int,
    ) -> None:
        self.root = root.resolve()
        self.max_upload_bytes = max_upload_bytes
        self.max_image_pixels = max_image_pixels
        self._staging_root = self.root / ".staging"

    async def stage(self, upload: UploadFile) -> StagedUpload:
        self._staging_root.mkdir(parents=True, exist_ok=True)
        path = self._staging_root / f"{uuid4().hex}.part"
        digest = hashlib.sha256()
        byte_size = 0

        try:
            with path.open("xb") as destination:
                while chunk := await upload.read(64 * 1024):
                    byte_size += len(chunk)
                    if byte_size > self.max_upload_bytes:
                        raise ImageTooLargeError(
                            f"Image exceeds the {self.max_upload_bytes}-byte upload limit"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise

        if byte_size == 0:
            path.unlink(missing_ok=True)
            raise InvalidImageError("Uploaded file is empty")

        return StagedUpload(path=path, byte_size=byte_size, sha256=digest.hexdigest())

    def validate(self, staged: StagedUpload, declared_mime_type: str) -> ValidatedImage:
        if declared_mime_type not in SUPPORTED_IMAGE_TYPES:
            raise UnsupportedImageTypeError(
                "Only JPEG, PNG, and WEBP images are supported"
            )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(staged.path) as image:
                    image_format = image.format
                    if image.width * image.height > self.max_image_pixels:
                        raise InvalidImageError(
                            f"Image exceeds the {self.max_image_pixels}-pixel safety limit"
                        )
                    image.verify()
                with Image.open(staged.path) as image:
                    image.load()
        except InvalidImageError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            ValueError,
        ) as exc:
            raise InvalidImageError("Uploaded bytes are not a valid image") from exc

        actual_mime_type = FORMAT_TO_MIME.get(image_format or "")
        if actual_mime_type is None:
            raise UnsupportedImageTypeError(
                "Only JPEG, PNG, and WEBP images are supported"
            )
        if actual_mime_type != declared_mime_type:
            raise UnsupportedImageTypeError(
                "Declared MIME type does not match the decoded image format"
            )
        return ValidatedImage(
            mime_type=actual_mime_type,
            image_format=image_format or "",
        )

    def promote(self, staged: StagedUpload, validated: ValidatedImage) -> str:
        extension = SUPPORTED_IMAGE_TYPES[validated.mime_type][1]
        storage_key = f"{staged.sha256[:2]}/{uuid4().hex}{extension}"
        destination = self.root / Path(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged.path, destination)
        return storage_key

    def discard(self, staged: StagedUpload) -> None:
        staged.path.unlink(missing_ok=True)

    def delete(self, storage_key: str) -> None:
        path = (self.root / Path(storage_key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage key resolves outside the image storage root")
        path.unlink(missing_ok=True)

    def get_validated_path(
        self,
        storage_key: str,
        *,
        expected_mime_type: str,
        expected_sha256: str,
        expected_byte_size: int,
    ) -> Path:
        path = (self.root / Path(storage_key)).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise InvalidStoredImageError("Stored image is missing or inaccessible")
        byte_size = path.stat().st_size
        if byte_size <= 0 or byte_size > self.max_upload_bytes:
            raise InvalidStoredImageError("Stored image no longer passes validation")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected_sha256:
            raise InvalidStoredImageError("Stored image integrity check failed")
        if byte_size != expected_byte_size:
            raise InvalidStoredImageError("Stored image no longer passes validation")
        try:
            self.validate(
                StagedUpload(path=path, byte_size=byte_size, sha256=digest),
                expected_mime_type,
            )
        except ImageStorageError as exc:
            raise InvalidStoredImageError(
                "Stored image no longer passes validation"
            ) from exc
        return path
