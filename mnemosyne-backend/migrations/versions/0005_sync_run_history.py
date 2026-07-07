"""Scheduled-run history for admin observability.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_run_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("newly_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_archived", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enqueued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_sync_run_history_finished_at", "sync_run_history", ["finished_at"]
    )


def downgrade() -> None:
    op.drop_table("sync_run_history")
