"""Add persisted labeled evaluation reports.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version", sa.String(length=50), nullable=False),
        sa.Column("config_version", sa.String(length=40), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=False),
        sa.Column("total_examples", sa.Integer(), nullable=False),
        sa.Column("eligible_recommendation_examples", sa.Integer(), nullable=False),
        sa.Column("correct_top1", sa.Integer(), nullable=False),
        sa.Column("incorrect_top1", sa.Integer(), nullable=False),
        sa.Column("correct_no_match", sa.Integer(), nullable=False),
        sa.Column("incorrect_refusals", sa.Integer(), nullable=False),
        sa.Column("safe_rejections", sa.Integer(), nullable=False),
        sa.Column("unsafe_acceptances", sa.Integer(), nullable=False),
        sa.Column("top1_precision", sa.Float(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "total_examples > 0", name="ck_evaluation_runs_total_positive"
        ),
        sa.CheckConstraint(
            "eligible_recommendation_examples >= 0 AND correct_top1 >= 0 AND "
            "incorrect_top1 >= 0 AND correct_no_match >= 0 AND "
            "incorrect_refusals >= 0 AND safe_rejections >= 0 AND "
            "unsafe_acceptances >= 0",
            name="ck_evaluation_runs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "top1_precision >= 0 AND top1_precision <= 1",
            name="ck_evaluation_runs_top1_precision",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_runs")
