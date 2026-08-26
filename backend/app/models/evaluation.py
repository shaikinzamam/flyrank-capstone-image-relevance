from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint("total_examples > 0", name="ck_evaluation_runs_total_positive"),
        CheckConstraint(
            "eligible_recommendation_examples >= 0 AND correct_top1 >= 0 AND "
            "incorrect_top1 >= 0 AND correct_no_match >= 0 AND "
            "incorrect_refusals >= 0 AND safe_rejections >= 0 AND "
            "unsafe_acceptances >= 0",
            name="ck_evaluation_runs_counts_nonnegative",
        ),
        CheckConstraint(
            "issued_recommendation_precision >= 0 AND "
            "issued_recommendation_precision <= 1",
            name="ck_evaluation_runs_issued_precision",
        ),
        Index("ix_evaluation_runs_workspace_created_at", "workspace_id", "created_at"),
        CheckConstraint(
            "top1_precision >= 0 AND top1_precision <= 1",
            name="ck_evaluation_runs_top1_precision",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(String(50))
    config_version: Mapped[str] = mapped_column(String(40))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    total_examples: Mapped[int] = mapped_column(Integer)
    eligible_recommendation_examples: Mapped[int] = mapped_column(Integer)
    correct_top1: Mapped[int] = mapped_column(Integer)
    incorrect_top1: Mapped[int] = mapped_column(Integer)
    correct_no_match: Mapped[int] = mapped_column(Integer)
    incorrect_refusals: Mapped[int] = mapped_column(Integer)
    safe_rejections: Mapped[int] = mapped_column(Integer)
    unsafe_acceptances: Mapped[int] = mapped_column(Integer)
    top1_precision: Mapped[float] = mapped_column(Float)
    issued_recommendation_precision: Mapped[float] = mapped_column(Float)
    report_json: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
