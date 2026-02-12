"""Add unit_system to user_settings.

Revision ID: 010_unit_system
Revises: 009_rls_indexes
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_unit_system"
down_revision: Union[str, None] = "009_rls_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "unit_system",
            sa.String(20),
            server_default="metric",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "unit_system")
