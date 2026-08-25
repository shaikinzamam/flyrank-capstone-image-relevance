"""Add append-only human recommendation reviews.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="ck_recommendation_reviews_decision",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_reviews_recommendation_id_created_at",
        "recommendation_reviews",
        ["recommendation_id", "created_at"],
    )
    op.create_index(
        "ix_recommendation_reviews_reviewer_id",
        "recommendation_reviews",
        ["reviewer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_reviews_reviewer_id",
        table_name="recommendation_reviews",
    )
    op.drop_index(
        "ix_recommendation_reviews_recommendation_id_created_at",
        table_name="recommendation_reviews",
    )
    op.drop_table("recommendation_reviews")
