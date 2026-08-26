"""Add workspace auth, async post jobs, and corrected evaluation metrics.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa
from uuid import UUID

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None

LEGACY_WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.execute(
        sa.text("INSERT INTO workspaces (id, name) VALUES (:id, :name)").bindparams(
            sa.bindparam("id", value=LEGACY_WORKSPACE_ID, type_=sa.Uuid()),
            sa.bindparam("name", value="Legacy Workspace", type_=sa.String()),
        )
    )
    op.create_table(
        "api_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(
        "ix_api_credentials_workspace_active",
        "api_credentials",
        ["workspace_id", "active"],
    )

    for table in ("image_assets", "posts", "processing_jobs", "ai_call_logs", "evaluation_runs"):
        op.add_column(table, sa.Column("workspace_id", sa.Uuid(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET workspace_id = :workspace_id").bindparams(
                sa.bindparam(
                    "workspace_id", value=LEGACY_WORKSPACE_ID, type_=sa.Uuid()
                )
            )
        )
        op.alter_column(table, "workspace_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_workspace_id",
            table,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_index("ix_image_assets_sha256", table_name="image_assets")
    op.create_index("ix_image_assets_sha256", "image_assets", ["sha256"])
    op.create_unique_constraint(
        "uq_image_assets_workspace_sha256",
        "image_assets",
        ["workspace_id", "sha256"],
    )
    op.create_index(
        "ix_posts_workspace_created_at", "posts", ["workspace_id", "created_at"]
    )
    op.create_index(
        "ix_ai_call_logs_workspace_created_at",
        "ai_call_logs",
        ["workspace_id", "created_at"],
    )

    op.drop_constraint(
        "processing_jobs_idempotency_key_key", "processing_jobs", type_="unique"
    )
    op.create_unique_constraint(
        "uq_jobs_workspace_idempotency",
        "processing_jobs",
        ["workspace_id", "idempotency_key"],
    )
    op.execute(
        "UPDATE processing_jobs SET job_type = 'image_processing' "
        "WHERE job_type = 'image_analysis'"
    )
    op.alter_column(
        "processing_jobs", "job_type", server_default="image_processing"
    )

    op.add_column("processing_job_items", sa.Column("post_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "processing_job_items_post_id_fkey",
        "processing_job_items",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("processing_job_items", "image_id", nullable=True)
    op.create_check_constraint(
        "ck_job_items_one_resource",
        "processing_job_items",
        "(image_id IS NOT NULL AND post_id IS NULL) OR "
        "(image_id IS NULL AND post_id IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_job_items_job_post", "processing_job_items", ["job_id", "post_id"]
    )

    op.add_column(
        "evaluation_runs",
        sa.Column("issued_recommendation_precision", sa.Float(), nullable=True),
    )
    op.execute(
        "UPDATE evaluation_runs SET issued_recommendation_precision = top1_precision"
    )
    op.execute(
        "UPDATE evaluation_runs SET top1_precision = "
        "CAST(correct_top1 AS DOUBLE PRECISION) / total_examples"
    )
    op.alter_column(
        "evaluation_runs", "issued_recommendation_precision", nullable=False
    )
    op.create_check_constraint(
        "ck_evaluation_runs_issued_precision",
        "evaluation_runs",
        "issued_recommendation_precision >= 0 AND issued_recommendation_precision <= 1",
    )
    op.create_index(
        "ix_evaluation_runs_workspace_created_at",
        "evaluation_runs",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_workspace_created_at", table_name="evaluation_runs")
    op.drop_constraint(
        "ck_evaluation_runs_issued_precision", "evaluation_runs", type_="check"
    )
    op.execute(
        "UPDATE evaluation_runs SET top1_precision = issued_recommendation_precision"
    )
    op.drop_column("evaluation_runs", "issued_recommendation_precision")

    op.execute("DELETE FROM processing_jobs WHERE job_type = 'post_embedding'")
    op.drop_constraint("uq_job_items_job_post", "processing_job_items", type_="unique")
    op.drop_constraint("ck_job_items_one_resource", "processing_job_items", type_="check")
    op.drop_constraint(
        "processing_job_items_post_id_fkey", "processing_job_items", type_="foreignkey"
    )
    op.drop_column("processing_job_items", "post_id")
    op.alter_column("processing_job_items", "image_id", nullable=False)
    op.execute(
        "UPDATE processing_jobs SET job_type = 'image_analysis' "
        "WHERE job_type = 'image_processing'"
    )
    op.alter_column("processing_jobs", "job_type", server_default="image_analysis")
    op.drop_constraint(
        "uq_jobs_workspace_idempotency", "processing_jobs", type_="unique"
    )
    op.create_unique_constraint(
        "processing_jobs_idempotency_key_key", "processing_jobs", ["idempotency_key"]
    )

    op.drop_constraint(
        "uq_image_assets_workspace_sha256", "image_assets", type_="unique"
    )
    op.drop_index("ix_image_assets_sha256", table_name="image_assets")
    op.create_index(
        "ix_image_assets_sha256", "image_assets", ["sha256"], unique=True
    )
    op.drop_index("ix_posts_workspace_created_at", table_name="posts")
    op.drop_index("ix_ai_call_logs_workspace_created_at", table_name="ai_call_logs")

    for table in reversed(
        ("image_assets", "posts", "processing_jobs", "ai_call_logs", "evaluation_runs")
    ):
        op.drop_constraint(f"fk_{table}_workspace_id", table, type_="foreignkey")
        op.drop_column(table, "workspace_id")

    op.drop_index("ix_api_credentials_workspace_active", table_name="api_credentials")
    op.drop_table("api_credentials")
    op.drop_table("workspaces")
