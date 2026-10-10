"""Operational metadata tables for data sources, jobs, audit logs, and artifacts.

Revision ID: 4b7c9d2e1f6a
Revises: 7e1b9c2f3b0a
Create Date: 2026-05-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "4b7c9d2e1f6a"
down_revision = "7e1b9c2f3b0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "municipality_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("provider_name", sa.String(length=200)),
        sa.Column(
            "governance_status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "publication_tier",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'restricted'"),
        ),
        sa.Column("refresh_frequency", sa.String(length=40)),
        sa.Column("last_refresh_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "configuration_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "name", name="uq_data_source_org_name"),
    )
    op.create_index("ix_data_sources_org_source_type", "data_sources", ["organization_id", "source_type"])
    op.create_index("ix_data_sources_org_municipality", "data_sources", ["organization_id", "municipality_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "municipality_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "submitted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("input_storage_uri", sa.Text()),
        sa.Column("manifest_storage_uri", sa.Text()),
        sa.Column("error_storage_uri", sa.Text()),
        sa.Column(
            "parameters_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "job_stats_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("queued_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ingestion_jobs_org_status", "ingestion_jobs", ["organization_id", "status"])
    op.create_index("ix_ingestion_jobs_source_status", "ingestion_jobs", ["source_id", "status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "municipality_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("target_id", sa.String(length=200)),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_org_created_at", "audit_logs", ["organization_id", "created_at"])
    op.create_index("ix_audit_logs_user_created_at", "audit_logs", ["user_id", "created_at"])

    op.create_table(
        "artifact_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "municipality_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("municipalities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "ingestion_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("artifact_kind", sa.String(length=120), nullable=False),
        sa.Column("artifact_name", sa.String(length=240), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=160)),
        sa.Column(
            "publication_tier",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'restricted'"),
        ),
        sa.Column(
            "lifecycle_status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "lineage_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "storage_uri", name="uq_artifact_reference_org_uri"),
    )
    op.create_index(
        "ix_artifact_references_org_kind",
        "artifact_references",
        ["organization_id", "artifact_kind"],
    )
    op.create_index(
        "ix_artifact_references_ingestion_job",
        "artifact_references",
        ["ingestion_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_references_ingestion_job", table_name="artifact_references")
    op.drop_index("ix_artifact_references_org_kind", table_name="artifact_references")
    op.drop_table("artifact_references")
    op.drop_index("ix_audit_logs_user_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_ingestion_jobs_source_status", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_org_status", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_data_sources_org_municipality", table_name="data_sources")
    op.drop_index("ix_data_sources_org_source_type", table_name="data_sources")
    op.drop_table("data_sources")
