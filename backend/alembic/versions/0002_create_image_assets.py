"""Create the image assets table.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "image_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "processing_status",
            sa.String(length=20),
            server_default="uploaded",
            nullable=False,
        ),
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
            "byte_size > 0",
            name="ck_image_assets_byte_size_positive",
        ),
        sa.CheckConstraint(
            "processing_status IN "
            "('uploaded', 'queued', 'processing', 'processed', 'failed')",
            name="ck_image_assets_processing_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_image_assets_sha256"),
        "image_assets",
        ["sha256"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_image_assets_sha256"), table_name="image_assets")
    op.drop_table("image_assets")
