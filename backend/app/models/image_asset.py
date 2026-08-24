from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProcessingStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ImageAsset(Base):
    __tablename__ = "image_assets"
    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_image_assets_byte_size_positive"),
        CheckConstraint(
            "processing_status IN "
            "('uploaded', 'queued', 'processing', 'processed', 'failed')",
            name="ck_image_assets_processing_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(32))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default=ProcessingStatus.UPLOADED.value,
        server_default=ProcessingStatus.UPLOADED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    metadata_record: Mapped["ImageMetadata | None"] = relationship(  # noqa: F821
        back_populates="image",
        cascade="all, delete-orphan",
        uselist=False,
    )
    embeddings: Mapped[list["ImageEmbedding"]] = relationship(  # noqa: F821
        back_populates="image", cascade="all, delete-orphan"
    )
