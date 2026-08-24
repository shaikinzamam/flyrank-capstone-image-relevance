"""Add posts and pgvector embedding persistence.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("expected_subject", sa.String(length=100), nullable=True),
        sa.Column("expected_category", sa.String(length=50), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("ai_call_logs", "image_id", nullable=True)
    op.add_column("ai_call_logs", sa.Column("post_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_ai_call_logs_post_id_posts",
        "ai_call_logs",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_ai_call_logs_one_resource",
        "ai_call_logs",
        "(image_id IS NOT NULL AND post_id IS NULL) OR "
        "(image_id IS NULL AND post_id IS NOT NULL)",
    )
    op.create_index(
        "ix_ai_call_logs_post_id_created_at",
        "ai_call_logs",
        ["post_id", "created_at"],
    )
    op.create_table(
        "image_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("vector", Vector(384), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("source_text_hash", sa.String(length=64), nullable=False),
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
            "dimensions = 384", name="ck_image_embeddings_dimensions"
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["image_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "image_id",
            "embedding_model",
            "embedding_version",
            name="uq_image_embeddings_image_model_version",
        ),
    )
    op.create_table(
        "post_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("vector", Vector(384), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("source_text_hash", sa.String(length=64), nullable=False),
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
            "dimensions = 384", name="ck_post_embeddings_dimensions"
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "post_id",
            "embedding_model",
            "embedding_version",
            name="uq_post_embeddings_post_model_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("post_embeddings")
    op.drop_table("image_embeddings")
    op.drop_index("ix_ai_call_logs_post_id_created_at", table_name="ai_call_logs")
    op.drop_constraint(
        "ck_ai_call_logs_one_resource", "ai_call_logs", type_="check"
    )
    op.drop_constraint(
        "fk_ai_call_logs_post_id_posts", "ai_call_logs", type_="foreignkey"
    )
    op.drop_column("ai_call_logs", "post_id")
    op.alter_column("ai_call_logs", "image_id", nullable=False)
    op.drop_table("posts")
