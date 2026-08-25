"""Add required tags and persisted guarded recommendations.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "required_tags",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.alter_column("posts", "required_tags", server_default=None)
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("matching_config_version", sa.String(length=40), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('matched', 'no_confident_match')",
            name="ck_recommendation_runs_status",
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_runs_post_id_created_at",
        "recommendation_runs",
        ["post_id", "created_at"],
    )
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("vision_confidence", sa.Float(), nullable=False),
        sa.Column("guard_decision", sa.String(length=40), nullable=False),
        sa.Column("guard_reason_code", sa.String(length=40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("expected_subject", sa.String(length=100), nullable=True),
        sa.Column("expected_category", sa.String(length=50), nullable=True),
        sa.Column("required_tags", sa.JSON(), nullable=False),
        sa.Column("candidate_subject", sa.String(length=100), nullable=False),
        sa.Column("candidate_subject_code", sa.String(length=64), nullable=False),
        sa.Column("candidate_category", sa.String(length=50), nullable=False),
        sa.Column("candidate_tags", sa.JSON(), nullable=False),
        sa.Column("metadata_valid", sa.Boolean(), nullable=False),
        sa.Column("is_low_confidence", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rank >= 1", name="ck_recommendations_rank_positive"),
        sa.CheckConstraint(
            "similarity_score >= -1 AND similarity_score <= 1",
            name="ck_recommendations_similarity",
        ),
        sa.CheckConstraint(
            "vision_confidence >= 0 AND vision_confidence <= 1",
            name="ck_recommendations_vision_confidence",
        ),
        sa.CheckConstraint(
            "guard_decision IN ('ACCEPTED', 'INVALID_METADATA', 'LOW_CONFIDENCE', "
            "'SUBJECT_MISMATCH', 'CATEGORY_MISMATCH', 'REQUIRED_TAG_MISSING', "
            "'LOW_SIMILARITY')",
            name="ck_recommendations_guard_decision",
        ),
        sa.ForeignKeyConstraint(["image_id"], ["image_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["recommendation_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendations_run_id_rank",
        "recommendations",
        ["run_id", "rank"],
        unique=True,
    )
    op.create_index(
        "ix_recommendations_post_id_created_at",
        "recommendations",
        ["post_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendations_post_id_created_at", table_name="recommendations")
    op.drop_index("ix_recommendations_run_id_rank", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index(
        "ix_recommendation_runs_post_id_created_at", table_name="recommendation_runs"
    )
    op.drop_table("recommendation_runs")
    op.drop_column("posts", "required_tags")
