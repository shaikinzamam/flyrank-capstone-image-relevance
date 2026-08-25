import json
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.models.image_asset import ProcessingStatus
from app.models.image_metadata import AiCallLog, ImageMetadata, MetadataStatus
from app.providers.vision import (
    ProviderConfigurationError,
    ProviderFailureError,
    ProviderTimeoutError,
    VisionProvider,
)
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.schemas.image_metadata import VisionMetadata
from app.services.image_assets import ImageNotFoundError
from app.services.image_storage import InvalidStoredImageError, LocalImageStorage


class ImageAnalysisError(Exception):
    pass


class ImageStateError(ImageAnalysisError):
    pass


class MalformedProviderResponseError(ImageAnalysisError):
    pass


class MetadataValidationError(ImageAnalysisError):
    pass


class VisionProviderTimeoutError(ImageAnalysisError):
    pass


class VisionProviderFailureError(ImageAnalysisError):
    pass


class VisionProviderConfigurationError(ImageAnalysisError):
    pass


class VisionBudgetExceededError(ImageAnalysisError):
    pass


class ImageAnalysisService:
    def __init__(
        self,
        image_repository: ImageAssetRepository,
        metadata_repository: ImageMetadataRepository,
        storage: LocalImageStorage,
        provider: VisionProvider,
        *,
        low_confidence_threshold: float,
        vision_budget_usd: float | None = None,
    ) -> None:
        self._images = image_repository
        self._metadata = metadata_repository
        self._storage = storage
        self._provider = provider
        self._low_confidence_threshold = low_confidence_threshold
        self._vision_budget_usd = vision_budget_usd

    def analyze(
        self,
        image_id: UUID,
        *,
        reprocess: bool,
        retry_count: int = 0,
        allow_processing: bool = False,
    ) -> tuple[ImageMetadata, bool]:
        asset = self._images.get(image_id)
        if asset is None:
            raise ImageNotFoundError("Image asset not found")

        existing = self._metadata.get_by_image_id(image_id)
        if existing is not None and not reprocess:
            return existing, True
        if (
            asset.processing_status == ProcessingStatus.PROCESSING.value
            and not allow_processing
        ):
            raise ImageStateError("Image analysis is already in progress")

        try:
            image_path = self._storage.get_validated_path(
                asset.storage_key,
                expected_mime_type=asset.mime_type,
                expected_sha256=asset.sha256,
                expected_byte_size=asset.byte_size,
            )
        except InvalidStoredImageError as exc:
            asset.processing_status = ProcessingStatus.FAILED.value
            self._images.commit()
            raise ImageStateError(str(exc)) from exc

        asset.processing_status = ProcessingStatus.PROCESSING.value
        self._images.commit()

        started = perf_counter()
        try:
            call_log = self._reserve_call(image_id, retry_count)
        except VisionBudgetExceededError:
            asset.processing_status = (
                ProcessingStatus.PROCESSED.value
                if existing is not None
                else ProcessingStatus.FAILED.value
            )
            self._metadata.commit()
            raise
        try:
            raw_output = self._provider.analyze(image_path, asset.mime_type)
        except ProviderConfigurationError as exc:
            self._record_failure(
                asset, existing, call_log, started, "provider_configuration"
            )
            raise VisionProviderConfigurationError(
                "Vision provider is not configured"
            ) from exc
        except ProviderTimeoutError as exc:
            self._record_failure(
                asset, existing, call_log, started, "provider_timeout"
            )
            raise VisionProviderTimeoutError("Vision provider timed out") from exc
        except ProviderFailureError as exc:
            self._record_failure(
                asset, existing, call_log, started, "provider_failure"
            )
            raise VisionProviderFailureError("Vision provider request failed") from exc
        except Exception as exc:
            self._record_failure(
                asset, existing, call_log, started, "provider_failure"
            )
            raise VisionProviderFailureError("Vision provider request failed") from exc

        try:
            payload = self._parse_output(raw_output)
        except MalformedProviderResponseError:
            self._record_failure(
                asset, existing, call_log, started, "malformed_response"
            )
            raise

        try:
            validated = VisionMetadata.model_validate(payload)
        except ValidationError as exc:
            self._record_failure(
                asset, existing, call_log, started, "schema_validation_failed"
            )
            raise MetadataValidationError(
                "Vision metadata failed schema validation"
            ) from exc

        is_low_confidence = validated.confidence < self._low_confidence_threshold
        values = validated.model_dump()
        if existing is None:
            metadata = ImageMetadata(image_id=image_id, **values)
            self._metadata.add(metadata)
        else:
            metadata = existing
            for field, value in values.items():
                setattr(metadata, field, value)
        metadata.is_low_confidence = is_low_confidence
        metadata.metadata_status = (
            MetadataStatus.FLAGGED.value
            if is_low_confidence
            else MetadataStatus.TRUSTED.value
        )
        metadata.vision_provider = self._provider.provider_name
        metadata.vision_model = self._provider.model_name
        metadata.schema_version = "1.0"
        asset.processing_status = ProcessingStatus.PROCESSED.value
        self._finish_call(call_log, started, "succeeded", None)
        self._metadata.commit()
        self._metadata.refresh(metadata)
        return metadata, False

    @staticmethod
    def _parse_output(raw_output: object) -> dict[str, Any]:
        if isinstance(raw_output, str):
            try:
                raw_output = json.loads(raw_output)
            except json.JSONDecodeError as exc:
                raise MalformedProviderResponseError(
                    "Vision provider returned malformed JSON"
                ) from exc
        if not isinstance(raw_output, dict):
            raise MalformedProviderResponseError(
                "Vision provider returned an invalid response shape"
            )
        return raw_output

    def _record_failure(
        self,
        asset: Any,
        existing: ImageMetadata | None,
        call_log: AiCallLog,
        started: float,
        error_code: str,
    ) -> None:
        asset.processing_status = (
            ProcessingStatus.PROCESSED.value
            if existing is not None
            else ProcessingStatus.FAILED.value
        )
        self._finish_call(call_log, started, "failed", error_code)
        self._metadata.commit()

    def _reserve_call(
        self,
        image_id: UUID,
        retry_count: int,
    ) -> AiCallLog:
        estimated_cost = self._provider.estimated_cost_usd
        if self._vision_budget_usd is not None:
            self._metadata.reserve_budget_lock()
            if estimated_cost is None:
                self._metadata.rollback()
                raise VisionBudgetExceededError(
                    "Vision budget is enabled but per-call cost is not configured"
                )
            if (
                self._metadata.total_estimated_cost() + estimated_cost
                > self._vision_budget_usd
            ):
                self._metadata.rollback()
                raise VisionBudgetExceededError("Vision processing budget is exhausted")
        call_log = AiCallLog(
            image_id=image_id,
            provider=self._provider.provider_name,
            model=self._provider.model_name,
            operation="vision_analyze",
            status="reserved",
            latency_ms=0,
            retry_count=retry_count,
            estimated_cost_usd=estimated_cost,
            error_code=None,
        )
        self._metadata.add_call_log(call_log)
        self._metadata.commit()
        return call_log

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
