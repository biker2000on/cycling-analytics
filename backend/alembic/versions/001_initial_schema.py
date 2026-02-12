"""Initial schema — users, activities, streams, laps, health_metrics.

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
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

    # ------------------------------------------------------------------
    # activities
    # ------------------------------------------------------------------
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("source", sa.Enum("fit_upload", "garmin", "strava", "manual", "csv", name="activity_source"), nullable=False),
        sa.Column("activity_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("sport_type", sa.String(100), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("distance_meters", sa.Numeric, nullable=True),
        sa.Column("elevation_gain_meters", sa.Numeric, nullable=True),
        sa.Column("avg_power_watts", sa.Numeric, nullable=True),
        sa.Column("max_power_watts", sa.Numeric, nullable=True),
        sa.Column("avg_hr", sa.Integer, nullable=True),
        sa.Column("max_hr", sa.Integer, nullable=True),
        sa.Column("avg_cadence", sa.Integer, nullable=True),
        sa.Column("calories", sa.Integer, nullable=True),
        sa.Column("tss", sa.Numeric, nullable=True),
        sa.Column("np_watts", sa.Numeric, nullable=True),
        sa.Column("intensity_factor", sa.Numeric, nullable=True),
        sa.Column("fit_file_path", sa.Text, nullable=True),
        sa.Column("device_name", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum("pending", "processing", "complete", "error", name="processing_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("file_hash", sa.Text, nullable=True),
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

    # ------------------------------------------------------------------
    # activity_streams (will become TimescaleDB hypertable)
    # ------------------------------------------------------------------
    op.create_table(
        "activity_streams",
        sa.Column(
            "activity_id",
            sa.Integer,
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer, nullable=True),
        sa.Column("power_watts", sa.Integer, nullable=True),
        sa.Column("heart_rate", sa.Integer, nullable=True),
        sa.Column("cadence", sa.Integer, nullable=True),
        sa.Column("speed_mps", sa.Numeric, nullable=True),
        sa.Column("altitude_meters", sa.Numeric, nullable=True),
        sa.Column("distance_meters", sa.Numeric, nullable=True),
        sa.Column("temperature_c", sa.Numeric, nullable=True),
        sa.Column(
            "position",
            geoalchemy2.Geography("POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("grade_percent", sa.Numeric, nullable=True),
        sa.PrimaryKeyConstraint("activity_id", "timestamp"),
    )

    # ------------------------------------------------------------------
    # activity_laps
    # ------------------------------------------------------------------
    op.create_table(
        "activity_laps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "activity_id",
            sa.Integer,
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lap_index", sa.Integer, nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_elapsed_time", sa.Numeric, nullable=False),
        sa.Column("total_distance", sa.Numeric, nullable=True),
        sa.Column("avg_power", sa.Numeric, nullable=True),
        sa.Column("max_power", sa.Numeric, nullable=True),
        sa.Column("avg_heart_rate", sa.Integer, nullable=True),
        sa.Column("max_heart_rate", sa.Integer, nullable=True),
        sa.Column("avg_cadence", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # health_metrics
    # ------------------------------------------------------------------
    op.create_table(
        "health_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("metric_type", sa.Enum("sleep_score", "weight_kg", "resting_hr", "hrv_ms", "body_battery", "stress_avg", name="metric_type"), nullable=False),
        sa.Column("value", sa.Numeric, nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("raw_data", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # TimescaleDB hypertable + compression
    # ------------------------------------------------------------------
    op.execute(
        "SELECT create_hypertable('activity_streams', 'timestamp', "
        "chunk_time_interval => INTERVAL '90 days', if_not_exists => TRUE);"
    )
    op.execute(
        "ALTER TABLE activity_streams SET ("
        "  timescaledb.compress,"
        "  timescaledb.compress_segmentby = 'activity_id',"
        "  timescaledb.compress_orderby = 'timestamp DESC'"
        ");"
    )
    op.execute(
        "SELECT add_compression_policy('activity_streams', INTERVAL '30 days');"
    )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------
    op.create_index(
        "ix_activities_user_date",
        "activities",
        ["user_id", sa.text("activity_date DESC")],
    )
    op.create_index(
        "ix_activities_external_id",
        "activities",
        ["external_id"],
        unique=True,
    )
    op.create_index(
        "ix_activities_file_hash",
        "activities",
        ["file_hash"],
    )
    op.create_index(
        "ix_activity_streams_activity_ts",
        "activity_streams",
        ["activity_id", "timestamp"],
    )
    op.create_index(
        "ix_activity_laps_activity_lap",
        "activity_laps",
        ["activity_id", "lap_index"],
    )
    op.create_index(
        "ix_health_metrics_user_date",
        "health_metrics",
        ["user_id", "date"],
    )

    # ------------------------------------------------------------------
    # Seed default user
    # ------------------------------------------------------------------
    op.execute(
        "INSERT INTO users (id, email, display_name, created_at, updated_at) "
        "VALUES (1, 'rider@localhost', 'Default Rider', now(), now());"
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("health_metrics")
    op.drop_table("activity_laps")
    op.drop_table("activity_streams")
    op.drop_table("activities")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS metric_type;")
    op.execute("DROP TYPE IF EXISTS processing_status;")
    op.execute("DROP TYPE IF EXISTS activity_source;")

    # Extensions are left in place (shared across databases)
