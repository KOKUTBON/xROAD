"""Core organization and municipality tables.

Revision ID: 7e1b9c2f3b0a
Revises: c0f2b6e54c2a
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7e1b9c2f3b0a"
down_revision = "c0f2b6e54c2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_subject", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320)),
        sa.Column("display_name", sa.String(length=200)),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_external_subject", "users", ["external_subject"], unique=True)

    op.create_table(
        "municipalities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("country_code", sa.String(length=4), nullable=False),
        sa.Column("region_code", sa.String(length=16)),
        sa.Column("province_code", sa.String(length=16)),
        sa.Column("city_code", sa.String(length=32)),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("country_code", "city_code", name="uq_municipality_country_city"),
    )
    op.create_index("ix_municipalities_slug", "municipalities", ["slug"], unique=True)

    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=60), nullable=False, server_default=sa.text("'analyst'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index(
        "ix_membership_org_user",
        "organization_memberships",
        ["organization_id", "user_id"],
        unique=True,
    )

    op.create_table(
        "organization_municipalities",
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
            sa.ForeignKey("municipalities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_level", sa.String(length=60), nullable=False, server_default=sa.text("'restricted'")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "municipality_id", name="uq_org_municipality"),
    )
    op.create_index(
        "ix_org_municipality",
        "organization_municipalities",
        ["organization_id", "municipality_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_org_municipality", table_name="organization_municipalities")
    op.drop_table("organization_municipalities")
    op.drop_index("ix_membership_org_user", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_index("ix_municipalities_slug", table_name="municipalities")
    op.drop_table("municipalities")
    op.drop_index("ix_users_external_subject", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
