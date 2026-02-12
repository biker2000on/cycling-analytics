"""Add import_batches table for bulk/archive import tracking.

Revision ID: 002_import_batch
Revises: 001_initial
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_import_batch"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processed_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "complete", "error", name="import_batch_status"),
            nullable=False,
            server_default="pending",
        ),
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
        "ix_import_batches_user_id",
        "import_batches",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("import_batches")
    op.execute("DROP TYPE IF EXISTS import_batch_status;")
