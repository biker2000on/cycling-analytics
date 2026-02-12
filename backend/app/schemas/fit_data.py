"""Pydantic schemas for FIT file parse results.

These schemas represent the structured output of the FIT parser.
They are intentionally decoupled from ORM models so the parser
remains a pure utility with no database dependency.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StreamRecord(BaseModel):
    """Single 1 Hz record from the FIT file's record messages."""

    timestamp: datetime
    elapsed_seconds: int | None = None
    power_watts: int | None = None
    heart_rate: int | None = None
    cadence: int | None = None
    speed_mps: Decimal | None = None
    altitude_meters: Decimal | None = None
    distance_meters: Decimal | None = None
    temperature_c: Decimal | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    grade_percent: Decimal | None = None


class LapRecord(BaseModel):
    """Single lap from the FIT file's lap messages."""

    lap_index: int
    start_time: datetime
    total_elapsed_time: Decimal | None = None
    total_distance: Decimal | None = None
    avg_power: Decimal | None = None
    max_power: Decimal | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_cadence: int | None = None
    lap_trigger: str | None = None


class ActivityData(BaseModel):
    """Summary-level metadata extracted from the FIT session message."""

    sport_type: str | None = None
    name: str | None = None
    activity_date: datetime | None = None
    duration_seconds: int | None = None
    distance_meters: Decimal | None = None
    elevation_gain_meters: Decimal | None = None
    avg_power_watts: Decimal | None = None
    max_power_watts: Decimal | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    avg_cadence: int | None = None
    calories: int | None = None
    device_name: str | None = None


class FitParseWarning(BaseModel):
    """Non-fatal warning emitted during FIT parsing."""

    message: str
    field: str | None = None
    value: str | None = Field(
        default=None,
        description="String representation of the problematic value",
    )


class FitParseResult(BaseModel):
    """Complete result of parsing a FIT file."""

    activity: ActivityData
    streams: list[StreamRecord]
    laps: list[LapRecord]
    warnings: list[FitParseWarning]
