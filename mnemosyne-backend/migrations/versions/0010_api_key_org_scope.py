"""Org-scoped API keys: nullable allowed_organizations column (#64).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# JSONB on Postgres, plain JSON elsewhere — mirrors models.JsonType.
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    # Nullable with no server default: existing keys read as NULL = unrestricted,
    # so the change is backward compatible (all current keys stay all-org).
    op.add_column(
        "api_keys",
        sa.Column("allowed_organizations", _JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "allowed_organizations")
