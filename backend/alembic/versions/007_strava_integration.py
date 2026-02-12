"""Add Strava OAuth2 columns to integrations table.

Revision ID: 007_strava_integration
Revises: 006_daily_fitness
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_strava_integration"
down_revision: Union[str, None] = "006_daily_fitness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integrations",
        sa.Column("access_token_encrypted", sa.LargeBinary, nullable=True),
    )
    op.add_column(
        "integrations",
        sa.Column("refresh_token_encrypted", sa.LargeBinary, nullable=True),
    )
    op.add_column(
        "integrations",
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "integrations",
        sa.Column("athlete_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("integrations", "athlete_id")
    op.drop_column("integrations", "token_expires_at")
    op.drop_column("integrations", "refresh_token_encrypted")
    op.drop_column("integrations", "access_token_encrypted")
