"""Phase 5.1: metrics time-series, milestones, issue delivery fields.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "issues",
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "issues",
        sa.Column("reopened_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "repository_metrics_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("captured_on", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_prs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merged_prs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("median_cycle_seconds", sa.Float(), nullable=True),
        sa.Column("health_overall", sa.Float(), nullable=True),
        sa.UniqueConstraint("repository_id", "captured_on", name="uq_snapshot_repo_day"),
    )
    op.create_index(
        "ix_metrics_snapshots_repo", "repository_metrics_snapshots", ["repository_id"]
    )

    op.create_table(
        "milestones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("due_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("repository_id", "number", name="uq_milestone_repo_number"),
    )
    op.create_index("ix_milestones_repo", "milestones", ["repository_id"])


def downgrade() -> None:
    op.drop_table("milestones")
    op.drop_table("repository_metrics_snapshots")
    op.drop_column("issues", "reopened_count")
    op.drop_column("issues", "first_response_at")
