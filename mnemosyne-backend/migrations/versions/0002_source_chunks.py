"""Phase 3: source-content columns on source_files + source_chunks table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_files", sa.Column("content", sa.Text(), nullable=True))
    op.add_column(
        "source_files",
        sa.Column("content_captured", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("source_files", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column(
        "source_files",
        sa.Column("quarantined", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("source_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_type", sa.String(20), nullable=False),
        sa.Column("symbol_name", sa.String(300), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index("ix_source_chunks_file_id", "source_chunks", ["file_id"])
    op.create_index("ix_source_chunks_repo", "source_chunks", ["repository_id"])
    op.create_index(
        "ix_source_chunks_symbol", "source_chunks", ["repository_id", "symbol_name"]
    )


def downgrade() -> None:
    op.drop_table("source_chunks")
    op.drop_column("source_files", "quarantined")
    op.drop_column("source_files", "content_hash")
    op.drop_column("source_files", "content_captured")
    op.drop_column("source_files", "content")
