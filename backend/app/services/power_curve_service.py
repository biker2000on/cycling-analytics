"""Power curve service -- compute mean-max power curve across all activities.

For each standard duration, finds the best effort across ALL activities in
the given date range. Results are cached in Redis.
"""

from datetime import date
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.metrics import PowerCurvePoint, PowerCurveResponse
from app.services.cache_service import CacheService
from app.utils.power_analysis import best_effort

logger = structlog.get_logger(__name__)

# Standard durations for the power curve (seconds)
STANDARD_DURATIONS = [
    1, 2, 3, 5, 10, 15, 20, 30, 45,
    60, 90, 120, 180, 240, 300, 360, 420, 480, 540,
    600, 720, 900, 1200, 1500, 1800, 2400, 3000, 3600,
]

POWER_CURVE_CACHE_TTL = 600  # 10 minutes


def power_curve_cache_key(user_id: int, start_date: str, end_date: str) -> str:
    """Build cache key for power curve data."""
    return f"power_curve:{user_id}:{start_date}:{end_date}"


async def _fetch_activities_with_power(
    user_id: int,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> list[dict]:
    """Fetch all activities with power data in the date range.

    Returns list of dicts with activity_id, activity_date.
    """
    query = text(
        """
        SELECT DISTINCT a.id AS activity_id, a.activity_date
        FROM activities a
        INNER JOIN activity_streams s ON s.activity_id = a.id
        WHERE a.user_id = :user_id
          AND a.activity_date >= :start_date
          AND a.activity_date <= :end_date
          AND s.power_watts IS NOT NULL
        ORDER BY a.activity_date
        """
    )
    result = await db.execute(query, {
        "user_id": user_id,
        "start_date": start_date,
        "end_date": end_date,
    })
    rows = result.fetchall()
    return [{"activity_id": row.activity_id, "activity_date": row.activity_date} for row in rows]


async def _fetch_power_stream(activity_id: int, db: AsyncSession) -> list[int | None]:
    """Fetch per-second power data for one activity."""
    query = text(
        """
        SELECT power_watts
        FROM activity_streams
        WHERE activity_id = :activity_id
        ORDER BY timestamp
        """
    )
    result = await db.execute(query, {"activity_id": activity_id})
    return [row.power_watts for row in result.fetchall()]


async def compute_power_curve(
    user_id: int,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> PowerCurveResponse:
    """Compute the mean-max power curve across all activities in date range.

    For each standard duration, finds the best effort across all activities.
    """
    activities = await _fetch_activities_with_power(user_id, start_date, end_date, db)

    if not activities:
        return PowerCurveResponse(
            data=[],
            start_date=start_date,
            end_date=end_date,
        )

    # For each duration, track the best effort across all activities
    best_by_duration: dict[int, tuple[Decimal, int, date]] = {}

    for act in activities:
        power_data = await _fetch_power_stream(act["activity_id"], db)
        if not power_data or len(power_data) < 1:
            continue

        for dur in STANDARD_DURATIONS:
            if dur > len(power_data):
                continue

            result = best_effort(power_data, dur)
            if result is None:
                continue

            watts, _ = result

            if dur not in best_by_duration or watts > best_by_duration[dur][0]:
                best_by_duration[dur] = (watts, act["activity_id"], act["activity_date"])

    # Build response
    points: list[PowerCurvePoint] = []
    for dur in STANDARD_DURATIONS:
        if dur in best_by_duration:
            watts, activity_id, activity_date = best_by_duration[dur]
            points.append(PowerCurvePoint(
                duration_seconds=dur,
                power_watts=watts,
                activity_id=activity_id,
                activity_date=activity_date,
            ))

    return PowerCurveResponse(
        data=points,
        start_date=start_date,
        end_date=end_date,
    )


async def get_power_curve_cached(
    user_id: int,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> PowerCurveResponse:
    """Get power curve with Redis caching."""
    settings = get_settings()
    cache = CacheService(redis_url=settings.REDIS_URL, db=settings.REDIS_CACHE_DB)
    cache_key = power_curve_cache_key(user_id, str(start_date), str(end_date))

    try:
        cached = await cache.get_json(cache_key)
        if cached is not None:
            logger.debug("cache_hit", key=cache_key)
            return PowerCurveResponse.model_validate(cached)
    finally:
        await cache.close()

    # Cache miss - compute
    response = await compute_power_curve(user_id, start_date, end_date, db)

    # Write to cache
    cache = CacheService(redis_url=settings.REDIS_URL, db=settings.REDIS_CACHE_DB)
    try:
        await cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            POWER_CURVE_CACHE_TTL,
        )
    finally:
        await cache.close()

    return response
