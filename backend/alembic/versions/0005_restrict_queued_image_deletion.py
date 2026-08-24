"""Prevent deletion of images referenced by durable job history.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_constraint(
        "processing_job_items_image_id_fkey",
        "processing_job_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "processing_job_items_image_id_fkey",
        "processing_job_items",
        "image_assets",
        ["image_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "processing_job_items_image_id_fkey",
        "processing_job_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "processing_job_items_image_id_fkey",
        "processing_job_items",
        "image_assets",
        ["image_id"],
        ["id"],
        ondelete="CASCADE",
    )
