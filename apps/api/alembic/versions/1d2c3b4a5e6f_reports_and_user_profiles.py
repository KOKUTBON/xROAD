"""Operational reports and user profile metadata.

Revision ID: 1d2c3b4a5e6f
Revises: 4b7c9d2e1f6a
Create Date: 2026-05-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "1d2c3b4a5e6f"
down_revision = "4b7c9d2e1f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("timezone_name", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("preferred_organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("preferred_municipality_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "profile_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_users_preferred_organization_id",
        "users",
        "organizations",
        ["preferred_organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_preferred_municipality_id",
        "users",
        "municipalities",
        ["preferred_municipality_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "reports",
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
            "generated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("report_type", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'draft'")),
        sa.Column(
            "visibility_tier",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'restricted'"),
        ),
        sa.Column("output_format", sa.String(length=40), nullable=False, server_default=sa.text("'pdf'")),
        sa.Column("file_storage_uri", sa.Text()),
        sa.Column(
            "parameters_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_reports_org_type", "reports", ["organization_id", "report_type"])
    op.create_index("ix_reports_org_status", "reports", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_reports_org_status", table_name="reports")
    op.drop_index("ix_reports_org_type", table_name="reports")
    op.drop_table("reports")

    op.drop_constraint("fk_users_preferred_municipality_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_preferred_organization_id", "users", type_="foreignkey")
    op.drop_column("users", "profile_json")
    op.drop_column("users", "preferred_municipality_id")
    op.drop_column("users", "preferred_organization_id")
    op.drop_column("users", "timezone_name")
    op.drop_column("users", "locale")
