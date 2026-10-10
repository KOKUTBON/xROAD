"""Intervention portfolio lifecycle fields.

Revision ID: 2a6f4c8d9e10
Revises: 9f2b6a1c4d8e
Create Date: 2026-06-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "2a6f4c8d9e10"
down_revision = "9f2b6a1c4d8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interventions", sa.Column("owner_subject", sa.String(length=200), nullable=True))
    op.add_column("interventions", sa.Column("planned_start_date", sa.Date(), nullable=True))
    op.add_column("interventions", sa.Column("planned_completion_date", sa.Date(), nullable=True))
    op.add_column("interventions", sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("interventions", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_interventions_owner_status", "interventions", ["owner_subject", "status"])


def downgrade() -> None:
    op.drop_index("ix_interventions_owner_status", table_name="interventions")
    op.drop_column("interventions", "notes")
    op.drop_column("interventions", "completed_at")
    op.drop_column("interventions", "planned_completion_date")
    op.drop_column("interventions", "planned_start_date")
    op.drop_column("interventions", "owner_subject")
