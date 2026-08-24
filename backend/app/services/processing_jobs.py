from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.processing_job import ProcessingJob, ProcessingJobItem
from app.repositories.image_assets import ImageAssetRepository
from app.repositories.processing_jobs import ProcessingJobRepository


class ProcessingJobNotFoundError(Exception):
    pass


class ProcessingImagesNotFoundError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class ProcessingJobService:
    def __init__(
        self,
        jobs: ProcessingJobRepository,
        images: ImageAssetRepository,
        *,
        max_attempts: int,
    ) -> None:
        self._jobs = jobs
        self._images = images
        self._max_attempts = max_attempts

    def create(
        self,
        image_ids: list[UUID],
        *,
        idempotency_key: str,
    ) -> tuple[ProcessingJob, bool]:
        existing = self._jobs.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            self._verify_same_request(existing, image_ids)
            return existing, True

        found_ids = {asset.id for asset in self._images.get_many(image_ids)}
        missing = set(image_ids) - found_ids
        if missing:
            raise ProcessingImagesNotFoundError(
                "One or more requested image assets were not found"
            )

        job = ProcessingJob(
            total_items=len(image_ids),
            idempotency_key=idempotency_key,
            items=[
                ProcessingJobItem(image_id=image_id, max_attempts=self._max_attempts)
                for image_id in image_ids
            ],
        )
        self._jobs.add(job)
        try:
            self._jobs.commit()
        except IntegrityError:
            self._jobs.rollback()
            existing = self._jobs.get_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            self._verify_same_request(existing, image_ids)
            return existing, True
        self._jobs.refresh(job)
        return job, False

    def get(self, job_id: UUID) -> ProcessingJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise ProcessingJobNotFoundError("Processing job not found")
        return job

    def list_items(self, job_id: UUID) -> list[ProcessingJobItem]:
        if self._jobs.get(job_id) is None:
            raise ProcessingJobNotFoundError("Processing job not found")
        return self._jobs.list_items(job_id)

    def _verify_same_request(
        self, existing: ProcessingJob, image_ids: list[UUID]
    ) -> None:
        if self._jobs.image_ids(existing.id) != set(image_ids):
            raise IdempotencyConflictError(
                "Idempotency key was already used for a different image set"
            )


def job_progress(job: ProcessingJob) -> float:
    terminal = job.processed_items + job.failed_items
    return round(terminal / job.total_items, 4)
