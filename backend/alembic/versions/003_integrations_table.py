"""Add integrations table for provider connections (Garmin, Strava, etc.).

Revision ID: 003_integrations
Revises: 002_import_batch
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_integrations"
down_revision: Union[str, None] = "002_import_batch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.Enum("garmin", "strava", name="integration_provider"),
            nullable=False,
        ),
        sa.Column("credentials_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "status",
            sa.Enum("active", "error", "disconnected", name="integration_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_integrations_user_provider",
        "integrations",
        ["user_id", "provider"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("integrations")
    op.execute("DROP TYPE IF EXISTS integration_status;")
    op.execute("DROP TYPE IF EXISTS integration_provider;")
