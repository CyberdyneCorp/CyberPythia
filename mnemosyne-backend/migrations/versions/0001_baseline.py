"""Baseline schema: extensions + all core tables.

Revision ID: 0001
Revises:
Create Date: 2026-07-07
"""

from alembic import op

from app.infrastructure.persistence.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # Greenfield baseline: create the full model schema in one shot.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
