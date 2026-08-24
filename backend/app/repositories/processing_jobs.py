from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.processing_job import (
    JobItemStatus,
    JobStatus,
    ProcessingJob,
    ProcessingJobItem,
)


@dataclass(frozen=True)
class ClaimedJobItem:
    id: UUID
    job_id: UUID
    image_id: UUID
    attempt_count: int
    max_attempts: int
    lease_token: UUID


class ProcessingJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: UUID) -> ProcessingJob | None:
        return self._session.get(ProcessingJob, job_id)

    def get_by_idempotency_key(self, key: str) -> ProcessingJob | None:
        return self._session.scalar(
            select(ProcessingJob).where(ProcessingJob.idempotency_key == key)
        )

    def list_items(self, job_id: UUID) -> list[ProcessingJobItem]:
        return list(
            self._session.scalars(
                select(ProcessingJobItem)
                .where(ProcessingJobItem.job_id == job_id)
                .order_by(ProcessingJobItem.id)
            )
        )

    def image_ids(self, job_id: UUID) -> set[UUID]:
        return set(
            self._session.scalars(
                select(ProcessingJobItem.image_id).where(
                    ProcessingJobItem.job_id == job_id
                )
            )
        )

    def add(self, job: ProcessingJob) -> None:
        self._session.add(job)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, job: ProcessingJob) -> None:
        self._session.refresh(job)

    def claim_next(self, *, worker_id: str, lease_seconds: int) -> ClaimedJobItem | None:
        now = datetime.now(timezone.utc)
        affected_jobs = self._fail_exhausted_expired_leases(now)
        for job_id in affected_jobs:
            self._refresh_job(job_id, now)

        item = self._session.scalar(
            select(ProcessingJobItem)
            .where(
                ProcessingJobItem.attempt_count < ProcessingJobItem.max_attempts,
                or_(
                    (
                        ProcessingJobItem.status.in_(
                            [
                                JobItemStatus.PENDING.value,
                                JobItemStatus.RETRY_SCHEDULED.value,
                            ]
                        )
                        & (ProcessingJobItem.available_at <= now)
                    ),
                    (
                        (ProcessingJobItem.status == JobItemStatus.PROCESSING.value)
                        & (ProcessingJobItem.leased_until <= now)
                    ),
                ),
            )
            .order_by(ProcessingJobItem.available_at, ProcessingJobItem.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item is None:
            self._session.commit()
            return None

        token = uuid4()
        item.status = JobItemStatus.PROCESSING.value
        item.attempt_count += 1
        item.started_at = item.started_at or now
        item.leased_until = now + timedelta(seconds=lease_seconds)
        item.lease_owner = worker_id
        item.lease_token = token

        job = self._session.get(ProcessingJob, item.job_id)
        if job is not None:
            job.status = JobStatus.RUNNING.value
            job.started_at = job.started_at or now
            job.completed_at = None
        self._session.commit()
        return ClaimedJobItem(
            id=item.id,
            job_id=item.job_id,
            image_id=item.image_id,
            attempt_count=item.attempt_count,
            max_attempts=item.max_attempts,
            lease_token=token,
        )

    def mark_succeeded(self, claimed: ClaimedJobItem) -> bool:
        item = self._owned_processing_item(claimed)
        if item is None:
            self._session.rollback()
            return False
        now = datetime.now(timezone.utc)
        item.status = JobItemStatus.SUCCEEDED.value
        item.completed_at = now
        item.last_error_code = None
        item.last_error_message = None
        self._clear_lease(item)
        self._session.flush()
        self._refresh_job(item.job_id, now)
        self._session.commit()
        return True

    def mark_transient_failure(
        self,
        claimed: ClaimedJobItem,
        *,
        error_code: str,
        error_message: str,
        backoff_seconds: int,
    ) -> bool:
        item = self._owned_processing_item(claimed)
        if item is None:
            self._session.rollback()
            return False
        now = datetime.now(timezone.utc)
        item.last_error_code = error_code
        item.last_error_message = error_message[:500]
        if item.attempt_count >= item.max_attempts:
            item.status = JobItemStatus.FAILED.value
            item.completed_at = now
        else:
            item.status = JobItemStatus.RETRY_SCHEDULED.value
            item.available_at = now + timedelta(seconds=backoff_seconds)
        self._clear_lease(item)
        self._session.flush()
        self._refresh_job(item.job_id, now)
        self._session.commit()
        return True

    def mark_permanent_failure(
        self,
        claimed: ClaimedJobItem,
        *,
        error_code: str,
        error_message: str,
    ) -> bool:
        item = self._owned_processing_item(claimed)
        if item is None:
            self._session.rollback()
            return False
        now = datetime.now(timezone.utc)
        item.status = JobItemStatus.FAILED.value
        item.completed_at = now
        item.last_error_code = error_code
        item.last_error_message = error_message[:500]
        self._clear_lease(item)
        self._session.flush()
        self._refresh_job(item.job_id, now)
        self._session.commit()
        return True

    def _owned_processing_item(
        self, claimed: ClaimedJobItem
    ) -> ProcessingJobItem | None:
        return self._session.scalar(
            select(ProcessingJobItem)
            .where(
                ProcessingJobItem.id == claimed.id,
                ProcessingJobItem.status == JobItemStatus.PROCESSING.value,
                ProcessingJobItem.lease_token == claimed.lease_token,
            )
            .with_for_update()
        )

    def _fail_exhausted_expired_leases(self, now: datetime) -> set[UUID]:
        items = list(
            self._session.scalars(
                select(ProcessingJobItem)
                .where(
                    ProcessingJobItem.status == JobItemStatus.PROCESSING.value,
                    ProcessingJobItem.leased_until <= now,
                    ProcessingJobItem.attempt_count >= ProcessingJobItem.max_attempts,
                )
                .with_for_update(skip_locked=True)
            )
        )
        affected: set[UUID] = set()
        for item in items:
            item.status = JobItemStatus.FAILED.value
            item.completed_at = now
            item.last_error_code = "lease_expired"
            item.last_error_message = "Worker lease expired after final attempt"
            self._clear_lease(item)
            affected.add(item.job_id)
        if items:
            self._session.flush()
        return affected

    def _refresh_job(self, job_id: UUID, now: datetime) -> None:
        job = self._session.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .with_for_update()
        )
        if job is None:
            return
        counts = dict(
            self._session.execute(
                select(ProcessingJobItem.status, func.count())
                .where(ProcessingJobItem.job_id == job_id)
                .group_by(ProcessingJobItem.status)
            ).all()
        )
        succeeded = counts.get(JobItemStatus.SUCCEEDED.value, 0)
        failed = counts.get(JobItemStatus.FAILED.value, 0)
        job.processed_items = succeeded
        job.failed_items = failed
        if succeeded + failed == job.total_items:
            job.completed_at = now
            if failed == 0:
                job.status = JobStatus.COMPLETED.value
                job.failure_summary = None
            elif succeeded == 0:
                job.status = JobStatus.FAILED.value
                job.failure_summary = f"All {failed} items failed"
            else:
                job.status = JobStatus.COMPLETED_WITH_ERRORS.value
                job.failure_summary = f"{failed} of {job.total_items} items failed"
        else:
            job.status = JobStatus.RUNNING.value

    @staticmethod
    def _clear_lease(item: ProcessingJobItem) -> None:
        item.leased_until = None
        item.lease_owner = None
        item.lease_token = None
