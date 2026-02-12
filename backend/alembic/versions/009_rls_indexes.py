"""Add composite indexes for data isolation and user profile fields.

Revision ID: 009_rls_indexes
Revises: 008_threshold_management
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_rls_indexes"
down_revision: Union[str, None] = "008_threshold_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite indexes for data isolation query performance
    # Use IF NOT EXISTS to handle partial re-runs gracefully
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_activities_user_date "
        "ON activities (user_id, activity_date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_daily_fitness_user_date_method "
        "ON daily_fitness (user_id, date, threshold_method)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_thresholds_user_method_date "
        "ON thresholds (user_id, method, effective_date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_health_metrics_user_date_type "
        "ON health_metrics (user_id, date, metric_type)"
    )

    # Add user profile fields for Phase 5
    op.add_column(
        "users",
        sa.Column("weight_kg", sa.Numeric, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("date_of_birth", sa.Date, nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(50),
            server_default="UTC",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "weight_kg")
    op.drop_index("ix_health_metrics_user_date_type", table_name="health_metrics")
    op.drop_index("ix_thresholds_user_method_date", table_name="thresholds")
    op.drop_index("ix_daily_fitness_user_date_method", table_name="daily_fitness")
    op.drop_index("ix_activities_user_date", table_name="activities")
