from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

JobStatusValue = Literal[
    "pending", "running", "completed", "completed_with_errors", "failed"
]
JobItemStatusValue = Literal[
    "pending", "processing", "retry_scheduled", "succeeded", "failed"
]


class CreateProcessingJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]
    idempotency_key: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ]

    @field_validator("image_ids")
    @classmethod
    def reject_duplicate_images(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("image_ids must not contain duplicates")
        return value


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: str
    status: JobStatusValue
    total_items: int
    processed_items: int
    failed_items: int
    progress: float
    idempotency_key: str
    failure_summary: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    reused: bool = False


class ProcessingJobItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    image_id: UUID
    status: JobItemStatusValue
    attempt_count: int
    max_attempts: int
    available_at: datetime
    last_error_code: str | None
    last_error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    leased_until: datetime | None
