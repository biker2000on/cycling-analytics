"""Add user_settings table for FTP, HR zones, and weight.

Revision ID: 004_user_settings
Revises: 003_integrations
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_user_settings"
down_revision: Union[str, None] = "003_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ftp_watts", sa.Numeric, nullable=True),
        sa.Column(
            "ftp_method",
            sa.String(50),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("ftp_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hr_zones", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("weight_kg", sa.Numeric, nullable=True),
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
        "ix_user_settings_user_id",
        "user_settings",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("user_settings")
