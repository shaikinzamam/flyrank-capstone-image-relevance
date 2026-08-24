import argparse
import logging
import os
import socket
import time
from typing import Any
from uuid import uuid4

from app.api.dependencies import get_image_storage, get_vision_provider
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.image_metadata import ImageMetadataRepository
from app.repositories.processing_jobs import (
    ClaimedJobItem,
    ProcessingJobRepository,
)
from app.services.image_analysis import (
    ImageAnalysisService,
    ImageStateError,
    MalformedProviderResponseError,
    MetadataValidationError,
    VisionBudgetExceededError,
    VisionProviderConfigurationError,
    VisionProviderFailureError,
    VisionProviderTimeoutError,
)
from app.services.image_assets import ImageNotFoundError

logger = logging.getLogger(__name__)


class ImageProcessingWorker:
    def __init__(
        self,
        worker_id: str | None = None,
        *,
        session_factory: Any = SessionLocal,
        settings: Any = None,
        provider: Any = None,
        storage: Any = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        )
        self._session_factory = session_factory
        self._provider = provider or get_vision_provider()
        self._storage = storage or get_image_storage()

    def process_one(self) -> bool:
        with self._session_factory() as session:
            jobs = ProcessingJobRepository(session)
            claimed = jobs.claim_next(
                worker_id=self._worker_id,
                lease_seconds=self._settings.processing_lease_seconds,
            )
            if claimed is None:
                return False

            analysis = ImageAnalysisService(
                ImageAssetRepository(session),
                ImageMetadataRepository(session),
                self._storage,
                self._provider,
                low_confidence_threshold=(
                    self._settings.vision_low_confidence_threshold
                ),
                vision_budget_usd=self._settings.vision_budget_usd,
            )
            try:
                analysis.analyze(
                    claimed.image_id,
                    reprocess=True,
                    retry_count=claimed.attempt_count - 1,
                    allow_processing=True,
                )
            except (VisionProviderTimeoutError, VisionProviderFailureError) as exc:
                jobs.mark_transient_failure(
                    claimed,
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                    backoff_seconds=self._backoff_seconds(claimed),
                )
            except (
                ImageNotFoundError,
                ImageStateError,
                MalformedProviderResponseError,
                MetadataValidationError,
                VisionBudgetExceededError,
                VisionProviderConfigurationError,
            ) as exc:
                jobs.mark_permanent_failure(
                    claimed,
                    error_code=self._error_code(exc),
                    error_message=str(exc),
                )
            except Exception as exc:
                logger.exception("Unexpected worker failure for item %s", claimed.id)
                jobs.mark_transient_failure(
                    claimed,
                    error_code="worker_failure",
                    error_message="Unexpected worker processing failure",
                    backoff_seconds=self._backoff_seconds(claimed),
                )
            else:
                jobs.mark_succeeded(claimed)
            return True

    def run(self) -> None:
        logger.info("Image processing worker %s started", self._worker_id)
        while True:
            if not self.process_one():
                time.sleep(self._settings.worker_poll_seconds)

    def _backoff_seconds(self, claimed: ClaimedJobItem) -> int:
        delay = self._settings.processing_initial_backoff_seconds * (
            2 ** (claimed.attempt_count - 1)
        )
        return min(delay, self._settings.processing_max_backoff_seconds)

    @staticmethod
    def _error_code(exc: Exception) -> str:
        names = {
            VisionProviderTimeoutError: "provider_timeout",
            VisionProviderFailureError: "provider_failure",
            VisionProviderConfigurationError: "provider_configuration",
            VisionBudgetExceededError: "budget_exhausted",
            MalformedProviderResponseError: "malformed_response",
            MetadataValidationError: "schema_validation_failed",
            ImageNotFoundError: "image_not_found",
            ImageStateError: "invalid_image_state",
        }
        return names.get(type(exc), "processing_failure")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process durable image-analysis jobs")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Claim at most one available item and exit",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    worker = ImageProcessingWorker()
    if args.once:
        worker.process_one()
    else:
        worker.run()


if __name__ == "__main__":
    main()
