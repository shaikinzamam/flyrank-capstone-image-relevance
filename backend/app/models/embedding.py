from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

EMBEDDING_DIMENSIONS = 384


class ImageEmbedding(Base):
    __tablename__ = "image_embeddings"
    __table_args__ = (
        CheckConstraint("dimensions = 384", name="ck_image_embeddings_dimensions"),
        UniqueConstraint(
            "image_id",
            "embedding_model",
            "embedding_version",
            name="uq_image_embeddings_image_model_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    image_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("image_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int] = mapped_column(Integer)
    source_text_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    image: Mapped["ImageAsset"] = relationship(  # noqa: F821
        back_populates="embeddings"
    )


class PostEmbedding(Base):
    __tablename__ = "post_embeddings"
    __table_args__ = (
        CheckConstraint("dimensions = 384", name="ck_post_embeddings_dimensions"),
        UniqueConstraint(
            "post_id",
            "embedding_model",
            "embedding_version",
            name="uq_post_embeddings_post_model_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int] = mapped_column(Integer)
    source_text_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    post: Mapped["Post"] = relationship(back_populates="embeddings")  # noqa: F821
