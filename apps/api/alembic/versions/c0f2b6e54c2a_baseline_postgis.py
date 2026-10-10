"""Baseline PostGIS extensions.

Revision ID: c0f2b6e54c2a
Revises:
Create Date: 2026-05-05 00:00:00.000000

"""
from alembic import op

revision = "c0f2b6e54c2a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    # Keep extensions on downgrade to avoid data loss in dependent objects.
    pass
