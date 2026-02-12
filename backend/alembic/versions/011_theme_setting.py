"""Add theme to user_settings.

Revision ID: 011_theme_setting
Revises: 010_unit_system
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_theme_setting"
down_revision: Union[str, None] = "010_unit_system"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "theme",
            sa.String(20),
            server_default="light",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "theme")
