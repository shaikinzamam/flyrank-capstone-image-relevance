from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetadataStatus(StrEnum):
    TRUSTED = "trusted"
    FLAGGED = "flagged"


class ImageMetadata(Base):
    __tablename__ = "image_metadata"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_image_metadata_confidence",
        ),
        CheckConstraint(
            "metadata_status IN ('trusted', 'flagged')",
            name="ck_image_metadata_status",
        ),
        Index("ix_image_metadata_subject_code", "subject_code"),
        Index("ix_image_metadata_category", "category"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    image_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("image_assets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(100))
    subject_code: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(50))
    caption: Mapped[str] = mapped_column(String(500))
    tags: Mapped[list[str]] = mapped_column(JSON)
    attributes: Mapped[list[str]] = mapped_column(JSON)
    objects: Mapped[list[str]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    is_low_confidence: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_status: Mapped[str] = mapped_column(String(20))
    vision_provider: Mapped[str] = mapped_column(String(50))
    vision_model: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    image: Mapped["ImageAsset"] = relationship(  # noqa: F821
        back_populates="metadata_record"
    )


class AiCallLog(Base):
    __tablename__ = "ai_call_logs"
    __table_args__ = (
        CheckConstraint(
            "latency_ms >= 0", name="ck_ai_call_logs_latency_nonnegative"
        ),
        CheckConstraint(
            "retry_count >= 0", name="ck_ai_call_logs_retry_nonnegative"
        ),
        Index("ix_ai_call_logs_image_id_created_at", "image_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    image_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("image_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(50), default="vision_analyze")
    status: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[int] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
