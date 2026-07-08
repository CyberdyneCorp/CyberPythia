"""Organization sync scope.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("login", sa.String(200), nullable=False, unique=True),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_organizations_login", "organizations", ["login"], unique=True)


def downgrade() -> None:
    op.drop_table("organizations")
