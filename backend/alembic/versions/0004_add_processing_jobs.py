"""Add durable image processing jobs and leased items.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_type",
            sa.String(length=40),
            server_default="image_analysis",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=30), server_default="pending", nullable=False
        ),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "total_items > 0", name="ck_processing_jobs_total_positive"
        ),
        sa.CheckConstraint(
            "processed_items >= 0 AND processed_items <= total_items",
            name="ck_processing_jobs_processed_range",
        ),
        sa.CheckConstraint(
            "failed_items >= 0 AND failed_items <= total_items",
            name="ck_processing_jobs_failed_range",
        ),
        sa.CheckConstraint(
            "processed_items + failed_items <= total_items",
            name="ck_processing_jobs_terminal_count",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', "
            "'completed_with_errors', 'failed')",
            name="ck_processing_jobs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_processing_jobs_status_created_at",
        "processing_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_table(
        "processing_job_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(length=30), server_default="pending", nullable=False
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_job_items_attempt_nonnegative"
        ),
        sa.CheckConstraint(
            "max_attempts > 0", name="ck_job_items_max_attempts_positive"
        ),
        sa.CheckConstraint(
            "attempt_count <= max_attempts", name="ck_job_items_attempt_range"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'retry_scheduled', "
            "'succeeded', 'failed')",
            name="ck_processing_job_items_status",
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["image_assets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["processing_jobs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "image_id", name="uq_job_items_job_image"),
    )
    op.create_index(
        "ix_job_items_claim",
        "processing_job_items",
        ["status", "available_at", "leased_until"],
        unique=False,
    )
    op.create_index(
        "ix_job_items_job_status",
        "processing_job_items",
        ["job_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_items_job_status", table_name="processing_job_items")
    op.drop_index("ix_job_items_claim", table_name="processing_job_items")
    op.drop_table("processing_job_items")
    op.drop_index("ix_processing_jobs_status_created_at", table_name="processing_jobs")
    op.drop_table("processing_jobs")
