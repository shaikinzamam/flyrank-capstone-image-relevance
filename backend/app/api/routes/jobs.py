from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ProcessingJobs
from app.schemas.processing_job import (
    ProcessingJobItemResponse,
    ProcessingJobResponse,
)
from app.services.processing_jobs import ProcessingJobNotFoundError, job_progress

router = APIRouter(prefix="/jobs", tags=["processing-jobs"])


def job_response(job, *, reused: bool = False) -> ProcessingJobResponse:
    return ProcessingJobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        total_items=job.total_items,
        processed_items=job.processed_items,
        failed_items=job.failed_items,
        progress=job_progress(job),
        idempotency_key=job.idempotency_key,
        failure_summary=job.failure_summary,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        reused=reused,
    )


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job(job_id: UUID, service: ProcessingJobs) -> ProcessingJobResponse:
    try:
        return job_response(service.get(job_id))
    except ProcessingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/{job_id}/items", response_model=list[ProcessingJobItemResponse])
def get_job_items(
    job_id: UUID, service: ProcessingJobs
) -> list[ProcessingJobItemResponse]:
    try:
        items = service.list_items(job_id)
    except ProcessingJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return [ProcessingJobItemResponse.model_validate(item) for item in items]
