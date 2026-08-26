from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (Index("ix_posts_workspace_created_at", "workspace_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    expected_subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    required_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    embeddings: Mapped[list["PostEmbedding"]] = relationship(  # noqa: F821
        back_populates="post", cascade="all, delete-orphan"
    )
    recommendation_runs: Mapped[list["RecommendationRun"]] = relationship(  # noqa: F821
        back_populates="post", cascade="all, delete-orphan"
    )
