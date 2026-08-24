"""Add structured vision metadata and AI call logs.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "image_metadata",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("subject_code", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("caption", sa.String(length=500), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("objects", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_low_confidence", sa.Boolean(), nullable=False),
        sa.Column("metadata_status", sa.String(length=20), nullable=False),
        sa.Column("vision_provider", sa.String(length=50), nullable=False),
        sa.Column("vision_model", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_image_metadata_confidence",
        ),
        sa.CheckConstraint(
            "metadata_status IN ('trusted', 'flagged')",
            name="ck_image_metadata_status",
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["image_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id"),
    )
    op.create_index(
        "ix_image_metadata_category", "image_metadata", ["category"], unique=False
    )
    op.create_index(
        "ix_image_metadata_subject_code",
        "image_metadata",
        ["subject_code"],
        unique=False,
    )
    op.create_table(
        "ai_call_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latency_ms >= 0", name="ck_ai_call_logs_latency_nonnegative"
        ),
        sa.CheckConstraint(
            "retry_count >= 0", name="ck_ai_call_logs_retry_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["image_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_call_logs_image_id_created_at",
        "ai_call_logs",
        ["image_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_call_logs_image_id_created_at", table_name="ai_call_logs")
    op.drop_table("ai_call_logs")
    op.drop_index("ix_image_metadata_subject_code", table_name="image_metadata")
    op.drop_index("ix_image_metadata_category", table_name="image_metadata")
    op.drop_table("image_metadata")
