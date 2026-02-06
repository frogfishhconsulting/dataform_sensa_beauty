"""migrate json columns to jsonb

Revision ID: 0002_jsonb
Revises: 0001_init
Create Date: 2026-02-05
"""

from __future__ import annotations

from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0002_jsonb"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # runs
    op.alter_column("runs", "config_json", type_=postgresql.JSONB(), postgresql_using="config_json::jsonb")
    op.alter_column("runs", "error_json", type_=postgresql.JSONB(), postgresql_using="error_json::jsonb")

    # documents
    op.alter_column("documents", "engagement_json", type_=postgresql.JSONB(), postgresql_using="engagement_json::jsonb")
    op.alter_column("documents", "raw_json", type_=postgresql.JSONB(), postgresql_using="raw_json::jsonb")

    # clusters
    op.alter_column("clusters", "evidence", type_=postgresql.JSONB(), postgresql_using="evidence::jsonb")

    # ad_assets
    op.alter_column("ad_assets", "rsa_sets", type_=postgresql.JSONB(), postgresql_using="rsa_sets::jsonb")
    op.alter_column("ad_assets", "final_selection", type_=postgresql.JSONB(), postgresql_using="final_selection::jsonb")
    op.alter_column("ad_assets", "qa_report", type_=postgresql.JSONB(), postgresql_using="qa_report::jsonb")

    # google_ads_pushes
    op.alter_column("google_ads_pushes", "request_payload", type_=postgresql.JSONB(), postgresql_using="request_payload::jsonb")
    op.alter_column("google_ads_pushes", "response_payload", type_=postgresql.JSONB(), postgresql_using="response_payload::jsonb")


def downgrade() -> None:
    # Down-migration back to JSON.
    op.alter_column("google_ads_pushes", "response_payload", type_=postgresql.JSON(), postgresql_using="response_payload::json")
    op.alter_column("google_ads_pushes", "request_payload", type_=postgresql.JSON(), postgresql_using="request_payload::json")

    op.alter_column("ad_assets", "qa_report", type_=postgresql.JSON(), postgresql_using="qa_report::json")
    op.alter_column("ad_assets", "final_selection", type_=postgresql.JSON(), postgresql_using="final_selection::json")
    op.alter_column("ad_assets", "rsa_sets", type_=postgresql.JSON(), postgresql_using="rsa_sets::json")

    op.alter_column("clusters", "evidence", type_=postgresql.JSON(), postgresql_using="evidence::json")

    op.alter_column("documents", "raw_json", type_=postgresql.JSON(), postgresql_using="raw_json::json")
    op.alter_column("documents", "engagement_json", type_=postgresql.JSON(), postgresql_using="engagement_json::json")

    op.alter_column("runs", "error_json", type_=postgresql.JSON(), postgresql_using="error_json::json")
    op.alter_column("runs", "config_json", type_=postgresql.JSON(), postgresql_using="config_json::json")

