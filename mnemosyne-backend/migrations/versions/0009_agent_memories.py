"""Agent-writable memory: repo/org-scoped notes.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("organization", sa.String(200), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False, server_default="note"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_memories_repository_id", "agent_memories", ["repository_id"])
    op.create_index("ix_agent_memories_organization", "agent_memories", ["organization"])


def downgrade() -> None:
    op.drop_table("agent_memories")
