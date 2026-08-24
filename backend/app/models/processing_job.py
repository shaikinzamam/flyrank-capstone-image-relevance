from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class JobItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint("total_items > 0", name="ck_processing_jobs_total_positive"),
        CheckConstraint(
            "processed_items >= 0 AND processed_items <= total_items",
            name="ck_processing_jobs_processed_range",
        ),
        CheckConstraint(
            "failed_items >= 0 AND failed_items <= total_items",
            name="ck_processing_jobs_failed_range",
        ),
        CheckConstraint(
            "processed_items + failed_items <= total_items",
            name="ck_processing_jobs_terminal_count",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', "
            "'completed_with_errors', 'failed')",
            name="ck_processing_jobs_status",
        ),
        Index("ix_processing_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    job_type: Mapped[str] = mapped_column(
        String(40), default="image_analysis", server_default="image_analysis"
    )
    status: Mapped[str] = mapped_column(
        String(30), default=JobStatus.PENDING.value, server_default="pending"
    )
    total_items: Mapped[int] = mapped_column(Integer)
    processed_items: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    failed_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items: Mapped[list["ProcessingJobItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class ProcessingJobItem(Base):
    __tablename__ = "processing_job_items"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_job_items_attempt_nonnegative"),
        CheckConstraint("max_attempts > 0", name="ck_job_items_max_attempts_positive"),
        CheckConstraint(
            "attempt_count <= max_attempts", name="ck_job_items_attempt_range"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'retry_scheduled', "
            "'succeeded', 'failed')",
            name="ck_processing_job_items_status",
        ),
        UniqueConstraint("job_id", "image_id", name="uq_job_items_job_image"),
        Index(
            "ix_job_items_claim",
            "status",
            "available_at",
            "leased_until",
        ),
        Index("ix_job_items_job_status", "job_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("image_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30), default=JobItemStatus.PENDING.value, server_default="pending"
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    leased_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    job: Mapped[ProcessingJob] = relationship(back_populates="items")
