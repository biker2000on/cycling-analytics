"""Add daily_fitness table for CTL/ATL/TSB tracking.

Revision ID: 006_daily_fitness
Revises: 005_activity_metrics
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_daily_fitness"
down_revision: Union[str, None] = "005_activity_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_fitness",
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column(
            "threshold_method",
            sa.String(50),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("tss_total", sa.Numeric, nullable=False, server_default="0"),
        sa.Column("activity_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ctl", sa.Numeric, nullable=False, server_default="0"),
        sa.Column("atl", sa.Numeric, nullable=False, server_default="0"),
        sa.Column("tsb", sa.Numeric, nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", "date", "threshold_method", name="pk_daily_fitness"),
    )

    op.create_index(
        "ix_daily_fitness_user_date",
        "daily_fitness",
        ["user_id", "date"],
    )


def downgrade() -> None:
    op.drop_table("daily_fitness")
