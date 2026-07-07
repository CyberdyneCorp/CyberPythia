"""Phase 4: connection kind + App columns, webhook_deliveries table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "github_connections",
        sa.Column("kind", sa.String(20), nullable=False, server_default="pat"),
    )
    # existing PAT rows keep their token; new App rows leave it null
    op.alter_column("github_connections", "encrypted_token", nullable=True)
    op.alter_column(
        "github_connections", "token_hint", nullable=False, server_default=""
    )
    op.add_column("github_connections", sa.Column("app_id", sa.String(50), nullable=True))
    op.add_column(
        "github_connections", sa.Column("installation_id", sa.String(50), nullable=True)
    )
    op.add_column(
        "github_connections", sa.Column("encrypted_private_key", sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        "github_connections",
        sa.Column("encrypted_webhook_secret", sa.LargeBinary(), nullable=True),
    )
    op.create_index(
        "ix_github_connections_installation",
        "github_connections",
        ["installation_id"],
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("delivery_id", sa.String(200), nullable=False, unique=True),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("action", sa.String(60), nullable=True),
        sa.Column("repository_full_name", sa.String(300), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_deliveries_delivery_id", "webhook_deliveries", ["delivery_id"])
    op.create_index("ix_webhook_deliveries_received_at", "webhook_deliveries", ["received_at"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_github_connections_installation", "github_connections")
    op.drop_column("github_connections", "encrypted_webhook_secret")
    op.drop_column("github_connections", "encrypted_private_key")
    op.drop_column("github_connections", "installation_id")
    op.drop_column("github_connections", "app_id")
    op.drop_column("github_connections", "kind")
