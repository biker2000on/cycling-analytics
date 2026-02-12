"""Pydantic schemas for activity stream API endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StreamDataPoint(BaseModel):
    """Single data point in a stream."""

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


class StreamStats(BaseModel):
    """Aggregated min/max/avg statistics across a stream."""

    power_avg: Decimal | None = None
    power_max: int | None = None
    hr_avg: int | None = None
    hr_max: int | None = None
    speed_avg: Decimal | None = None
    speed_max: Decimal | None = None
    altitude_min: Decimal | None = None
    altitude_max: Decimal | None = None


class StreamResponse(BaseModel):
    """Complete stream data for an activity (columnar format).

    Columnar layout is intentional -- more efficient for frontend charting
    libraries that consume arrays per channel.
    """

    activity_id: int
    point_count: int
    stats: StreamStats
    timestamps: list[datetime]
    power: list[int | None]
    heart_rate: list[int | None]
    cadence: list[int | None]
    speed_mps: list[Decimal | None]
    altitude_meters: list[Decimal | None]
    distance_meters: list[Decimal | None]
    temperature_c: list[Decimal | None]
    latitude: list[Decimal | None]
    longitude: list[Decimal | None]
    grade_percent: list[Decimal | None]


class StreamSummaryResponse(BaseModel):
    """Downsampled stream data for chart display.

    Uses LTTB (Largest Triangle Three Buckets) to preserve visual shape
    while reducing point count.
    """

    activity_id: int
    point_count: int
    original_point_count: int
    stats: StreamStats
    timestamps: list[datetime]
    power: list[int | None]
    heart_rate: list[int | None]
    cadence: list[int | None]
    speed_mps: list[Decimal | None]
    altitude_meters: list[Decimal | None]


class ZoneBlock(BaseModel):
    """A 30-second block classified into a power zone."""

    start_seconds: int = Field(..., description="Start time in seconds from activity start")
    end_seconds: int = Field(..., description="End time in seconds from activity start")
    zone: int = Field(..., ge=1, le=7, description="Power zone (1-7)")
    avg_power: Decimal = Field(..., description="Average power in watts for this block")


class ZoneBlocksResponse(BaseModel):
    """Pre-computed 30-second zone blocks for an activity."""

    activity_id: int
    ftp: int = Field(..., description="FTP used for zone calculation")
    blocks: list[ZoneBlock] = Field(default_factory=list)
    total_blocks: int = Field(0, description="Total number of blocks")
