"""Add thresholds table and extend user_settings for Phase 4.

Revision ID: 008_threshold_management
Revises: 007_strava_integration
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_threshold_management"
down_revision: Union[str, None] = "007_strava_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create thresholds table
    op.create_table(
        "thresholds",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("ftp_watts", sa.Numeric, nullable=False),
        sa.Column(
            "source_activity_id",
            sa.Integer,
            sa.ForeignKey("activities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_thresholds_user_method_date",
        "thresholds",
        ["user_id", "method", "effective_date"],
    )
    # Index for common query patterns
    op.create_index(
        "ix_thresholds_user_method_active",
        "thresholds",
        ["user_id", "method", "is_active"],
    )

    # Extend user_settings for Phase 4.5
    op.add_column(
        "user_settings",
        sa.Column(
            "preferred_threshold_method",
            sa.String(50),
            server_default="manual",
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "calendar_start_day",
            sa.Integer,
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column("date_of_birth", sa.Date, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "date_of_birth")
    op.drop_column("user_settings", "calendar_start_day")
    op.drop_column("user_settings", "preferred_threshold_method")
    op.drop_index("ix_thresholds_user_method_active", table_name="thresholds")
    op.drop_constraint("uq_thresholds_user_method_date", "thresholds", type_="unique")
    op.drop_table("thresholds")
