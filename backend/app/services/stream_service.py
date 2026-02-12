"""Stream data service — query, aggregate, downsample, and route extraction.

All heavy lifting for the /streams and /route endpoints lives here.
"""

import json
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.route import RouteGeoJSON
from app.schemas.stream import StreamResponse, StreamStats, StreamSummaryResponse
from app.utils.lttb import lttb_downsample

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_avg(values: list[Any]) -> Decimal | None:
    """Compute the average of non-None numeric values, returning Decimal."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    total = sum(Decimal(str(v)) for v in filtered)
    return total / Decimal(len(filtered))


def _safe_max_int(values: list[Any]) -> int | None:
    filtered = [v for v in values if v is not None]
    return max(filtered) if filtered else None


def _safe_max_decimal(values: list[Any]) -> Decimal | None:
    filtered = [Decimal(str(v)) for v in values if v is not None]
    return max(filtered) if filtered else None


def _safe_min_decimal(values: list[Any]) -> Decimal | None:
    filtered = [Decimal(str(v)) for v in values if v is not None]
    return min(filtered) if filtered else None


def _compute_stats(
    power: list[int | None],
    heart_rate: list[int | None],
    speed_mps: list[Decimal | None],
    altitude_meters: list[Decimal | None],
) -> StreamStats:
    """Derive StreamStats from columnar lists."""
    return StreamStats(
        power_avg=_safe_avg(power),
        power_max=_safe_max_int(power),
        hr_avg=_safe_avg(heart_rate),
        hr_max=_safe_max_int(heart_rate),
        speed_avg=_safe_avg(speed_mps),
        speed_max=_safe_max_decimal(speed_mps),
        altitude_min=_safe_min_decimal(altitude_meters),
        altitude_max=_safe_max_decimal(altitude_meters),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_activity_streams(
    activity_id: int,
    db: AsyncSession,
) -> StreamResponse:
    """Fetch all stream records for an activity and return columnar data.

    Uses raw SQL with PostGIS functions to extract lat/lon from the
    Geography POINT column.
    """
    query = text(
        """
        SELECT
            timestamp,
            elapsed_seconds,
            power_watts,
            heart_rate,
            cadence,
            speed_mps,
            altitude_meters,
            distance_meters,
            temperature_c,
            ST_Y(position::geometry) AS latitude,
            ST_X(position::geometry) AS longitude,
            grade_percent
        FROM activity_streams
        WHERE activity_id = :activity_id
        ORDER BY timestamp
        """
    )

    result = await db.execute(query, {"activity_id": activity_id})
    rows = result.fetchall()

    # Build columnar arrays
    timestamps = []
    power = []
    heart_rate = []
    cadence = []
    speed_mps = []
    altitude_meters = []
    distance_meters = []
    temperature_c = []
    latitude = []
    longitude = []
    grade_percent = []

    for row in rows:
        timestamps.append(row.timestamp)
        power.append(row.power_watts)
        heart_rate.append(row.heart_rate)
        cadence.append(row.cadence)
        speed_mps.append(
            Decimal(str(row.speed_mps)) if row.speed_mps is not None else None
        )
        altitude_meters.append(
            Decimal(str(row.altitude_meters)) if row.altitude_meters is not None else None
        )
        distance_meters.append(
            Decimal(str(row.distance_meters)) if row.distance_meters is not None else None
        )
        temperature_c.append(
            Decimal(str(row.temperature_c)) if row.temperature_c is not None else None
        )
        latitude.append(
            Decimal(str(row.latitude)) if row.latitude is not None else None
        )
        longitude.append(
            Decimal(str(row.longitude)) if row.longitude is not None else None
        )
        grade_percent.append(
            Decimal(str(row.grade_percent)) if row.grade_percent is not None else None
        )

    stats = _compute_stats(power, heart_rate, speed_mps, altitude_meters)

    logger.info(
        "streams_fetched",
        activity_id=activity_id,
        point_count=len(timestamps),
    )

    return StreamResponse(
        activity_id=activity_id,
        point_count=len(timestamps),
        stats=stats,
        timestamps=timestamps,
        power=power,
        heart_rate=heart_rate,
        cadence=cadence,
        speed_mps=speed_mps,
        altitude_meters=altitude_meters,
        distance_meters=distance_meters,
        temperature_c=temperature_c,
        latitude=latitude,
        longitude=longitude,
        grade_percent=grade_percent,
    )


async def get_activity_streams_summary(
    activity_id: int,
    points: int,
    db: AsyncSession,
) -> StreamSummaryResponse:
    """Return a downsampled version of the activity streams.

    Uses LTTB on the power channel as the primary signal to select which
    time indices to keep.  All other channels are sampled at the same
    indices so the data remains aligned.
    """
    full = await get_activity_streams(activity_id, db)
    original_count = full.point_count

    if original_count <= points:
        # No downsampling needed — return everything (in summary shape).
        return StreamSummaryResponse(
            activity_id=activity_id,
            point_count=original_count,
            original_point_count=original_count,
            stats=full.stats,
            timestamps=full.timestamps,
            power=full.power,
            heart_rate=full.heart_rate,
            cadence=full.cadence,
            speed_mps=full.speed_mps,
            altitude_meters=full.altitude_meters,
        )

    # Build (x, y) pairs for LTTB.  Use elapsed index as x, power as y.
    # Treat None power values as 0 for downsampling selection purposes.
    lttb_data: list[tuple[float, float]] = [
        (float(i), float(full.power[i] or 0))
        for i in range(original_count)
    ]

    indices = lttb_downsample(lttb_data, points)

    return StreamSummaryResponse(
        activity_id=activity_id,
        point_count=len(indices),
        original_point_count=original_count,
        stats=full.stats,
        timestamps=[full.timestamps[i] for i in indices],
        power=[full.power[i] for i in indices],
        heart_rate=[full.heart_rate[i] for i in indices],
        cadence=[full.cadence[i] for i in indices],
        speed_mps=[full.speed_mps[i] for i in indices],
        altitude_meters=[full.altitude_meters[i] for i in indices],
    )


async def get_activity_route(
    activity_id: int,
    db: AsyncSession,
    activity_name: str = "",
    sport_type: str | None = None,
) -> RouteGeoJSON | None:
    """Build a GeoJSON Feature with a LineString from GPS stream data.

    Uses PostGIS ``ST_MakeLine`` to aggregate ordered points into a line,
    then ``ST_AsGeoJSON`` for serialisation.

    Returns ``None`` if the activity has no GPS data.
    """
    query = text(
        """
        SELECT ST_AsGeoJSON(
            ST_MakeLine(position::geometry ORDER BY timestamp)
        ) AS geojson
        FROM activity_streams
        WHERE activity_id = :activity_id
          AND position IS NOT NULL
        """
    )
    result = await db.execute(query, {"activity_id": activity_id})
    row = result.fetchone()

    if row is None or row.geojson is None:
        return None

    geometry = json.loads(row.geojson)

    return RouteGeoJSON(
        type="Feature",
        geometry=geometry,
        properties={
            "activity_id": activity_id,
            "name": activity_name,
            "sport_type": sport_type,
        },
    )
