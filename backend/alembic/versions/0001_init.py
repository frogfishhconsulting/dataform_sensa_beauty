"""init

Revision ID: 0001_init
Revises: 
Create Date: 2026-02-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("recency_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("queued", "collecting", "analyzing", "drafting", "awaiting_approval", "pushing", "complete", "failed", name="run_status"), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.Enum("reddit", "x", "youtube", name="platform"), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("engagement_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_index("ix_documents_run_id", "documents", ["run_id"])
    op.create_index("ix_documents_platform", "documents", ["platform"])

    op.create_table(
        "clusters",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Enum("pain_point", "highlight", name="cluster_type"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("intensity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_clusters_run_id", "clusters", ["run_id"])
    op.create_index("ix_clusters_type", "clusters", ["type"])

    op.create_table(
        "ad_assets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rsa_sets", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("final_selection", sa.JSON(), nullable=True),
        sa.Column("qa_report", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ad_assets_run_id", "ad_assets", ["run_id"])

    op.create_table(
        "google_ads_pushes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("ad_group_id", sa.String(), nullable=False),
        sa.Column("status", sa.Enum("dry_run_ok", "pushed", "failed", name="push_status"), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("response_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_google_ads_pushes_run_id", "google_ads_pushes", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_google_ads_pushes_run_id", table_name="google_ads_pushes")
    op.drop_table("google_ads_pushes")
    op.drop_index("ix_ad_assets_run_id", table_name="ad_assets")
    op.drop_table("ad_assets")
    op.drop_index("ix_clusters_type", table_name="clusters")
    op.drop_index("ix_clusters_run_id", table_name="clusters")
    op.drop_table("clusters")
    op.drop_index("ix_documents_platform", table_name="documents")
    op.drop_index("ix_documents_run_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("runs")
    op.execute("DROP TYPE IF EXISTS push_status;")
    op.execute("DROP TYPE IF EXISTS cluster_type;")
    op.execute("DROP TYPE IF EXISTS platform;")
    op.execute("DROP TYPE IF EXISTS run_status;")

