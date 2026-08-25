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
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecommendationRunStatus(StrEnum):
    MATCHED = "matched"
    NO_CONFIDENT_MATCH = "no_confident_match"


class GuardDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    INVALID_METADATA = "INVALID_METADATA"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    SUBJECT_MISMATCH = "SUBJECT_MISMATCH"
    CATEGORY_MISMATCH = "CATEGORY_MISMATCH"
    REQUIRED_TAG_MISSING = "REQUIRED_TAG_MISSING"
    LOW_SIMILARITY = "LOW_SIMILARITY"


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('matched', 'no_confident_match')",
            name="ck_recommendation_runs_status",
        ),
        Index("ix_recommendation_runs_post_id_created_at", "post_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    matching_config_version: Mapped[str] = mapped_column(String(40))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    post: Mapped["Post"] = relationship(back_populates="recommendation_runs")  # noqa: F821
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Recommendation.rank"
    )


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("rank >= 1", name="ck_recommendations_rank_positive"),
        CheckConstraint(
            "similarity_score >= -1 AND similarity_score <= 1",
            name="ck_recommendations_similarity",
        ),
        CheckConstraint(
            "vision_confidence >= 0 AND vision_confidence <= 1",
            name="ck_recommendations_vision_confidence",
        ),
        CheckConstraint(
            "guard_decision IN ('ACCEPTED', 'INVALID_METADATA', 'LOW_CONFIDENCE', "
            "'SUBJECT_MISMATCH', 'CATEGORY_MISMATCH', 'REQUIRED_TAG_MISSING', "
            "'LOW_SIMILARITY')",
            name="ck_recommendations_guard_decision",
        ),
        Index("ix_recommendations_run_id_rank", "run_id", "rank", unique=True),
        Index("ix_recommendations_post_id_created_at", "post_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("recommendation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    post_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    image_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("image_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer)
    similarity_score: Mapped[float] = mapped_column(Float)
    vision_confidence: Mapped[float] = mapped_column(Float)
    guard_decision: Mapped[str] = mapped_column(String(40))
    guard_reason_code: Mapped[str] = mapped_column(String(40))
    explanation: Mapped[str] = mapped_column(Text)
    expected_subject: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    required_tags: Mapped[list[str]] = mapped_column(JSON)
    candidate_subject: Mapped[str] = mapped_column(String(100))
    candidate_subject_code: Mapped[str] = mapped_column(String(64))
    candidate_category: Mapped[str] = mapped_column(String(50))
    candidate_tags: Mapped[list[str]] = mapped_column(JSON)
    metadata_valid: Mapped[bool] = mapped_column(Boolean)
    is_low_confidence: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    run: Mapped[RecommendationRun] = relationship(back_populates="recommendations")
