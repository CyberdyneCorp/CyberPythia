"""Readiness gate time-series snapshots.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repository_readiness_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("captured_on", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gate", sa.String(16), nullable=False),
        sa.UniqueConstraint("repository_id", "captured_on"),
    )
    op.create_index(
        "ix_repository_readiness_snapshots_repository_id",
        "repository_readiness_snapshots",
        ["repository_id"],
    )


def downgrade() -> None:
    op.drop_table("repository_readiness_snapshots")
