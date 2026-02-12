"""Add activity_metrics table for computed Coggan metrics.

Revision ID: 005_activity_metrics
Revises: 004_user_settings
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_activity_metrics"
down_revision: Union[str, None] = "004_user_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "activity_id",
            sa.Integer,
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ftp_at_computation", sa.Numeric, nullable=False),
        sa.Column("normalized_power", sa.Numeric, nullable=True),
        sa.Column("tss", sa.Numeric, nullable=True),
        sa.Column("intensity_factor", sa.Numeric, nullable=True),
        sa.Column("zone_distribution", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("variability_index", sa.Numeric, nullable=True),
        sa.Column("efficiency_factor", sa.Numeric, nullable=True),
        sa.Column(
            "threshold_method",
            sa.String(50),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_activity_metrics_activity_method",
        "activity_metrics",
        ["activity_id", "threshold_method"],
        unique=True,
    )

    op.create_index(
        "ix_activity_metrics_user_id",
        "activity_metrics",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("activity_metrics")
