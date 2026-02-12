"""Threshold estimation service -- auto-detect FTP from ride history.

Supports multiple estimation methods:
- pct_20min: 95% of best 20-minute power
- pct_8min: 90% of best 8-minute power
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_stream import ActivityStream
from app.models.threshold import Threshold
from app.utils.power_analysis import best_effort

logger = structlog.get_logger(__name__)

# Estimation constants
TWENTY_MIN_SECONDS = 1200
EIGHT_MIN_SECONDS = 480
PCT_20MIN_FACTOR = Decimal("0.95")
PCT_8MIN_FACTOR = Decimal("0.90")


async def _find_best_effort_across_activities(
    user_id: int,
    duration_seconds: int,
    db: AsyncSession,
) -> tuple[Decimal, int, date] | None:
    """Search all activities for the best power effort of given duration.

    Returns:
        Tuple of (best_avg_power, activity_id, activity_date) or None.
    """
    # Fetch all activities for the user that have stream data
    activity_stmt = (
        select(Activity.id, Activity.activity_date, Activity.duration_seconds)
        .where(
            Activity.user_id == user_id,
            Activity.duration_seconds >= duration_seconds,
        )
        .order_by(Activity.activity_date.desc())
    )
    activity_result = await db.execute(activity_stmt)
    activities = activity_result.fetchall()

    if not activities:
        return None

    best_power: Decimal | None = None
    best_activity_id: int | None = None
    best_activity_date: date | None = None

    for row in activities:
        activity_id = row.id
        activity_date = row.activity_date

        # Fetch power stream for this activity
        stream_stmt = (
            select(ActivityStream.power_watts)
            .where(ActivityStream.activity_id == activity_id)
            .order_by(ActivityStream.timestamp)
        )
        stream_result = await db.execute(stream_stmt)
        power_rows = stream_result.fetchall()

        if not power_rows:
            continue

        power_data: list[int | None] = [r.power_watts for r in power_rows]

        effort = best_effort(power_data, duration_seconds)
        if effort is not None:
            avg_power, _ = effort
            if best_power is None or avg_power > best_power:
                best_power = avg_power
                best_activity_id = activity_id
                # Convert activity_date to date if it's datetime
                if hasattr(activity_date, "date"):
                    best_activity_date = activity_date.date()
                else:
                    best_activity_date = activity_date

    if best_power is None or best_activity_id is None or best_activity_date is None:
        return None

    return (best_power, best_activity_id, best_activity_date)


async def estimate_threshold_20min(
    user_id: int,
    db: AsyncSession,
) -> Threshold | None:
    """Estimate FTP as 95% of the best 20-minute power effort.

    Searches all activities with stream data to find the highest
    20-minute average power, then applies the 0.95 factor.

    Returns:
        A new (uncommitted) Threshold record, or None if no qualifying rides.
    """
    log = logger.bind(user_id=user_id, method="pct_20min")

    result = await _find_best_effort_across_activities(
        user_id, TWENTY_MIN_SECONDS, db
    )

    if result is None:
        log.info("no_qualifying_rides", min_duration=TWENTY_MIN_SECONDS)
        return None

    best_power, activity_id, activity_date = result
    ftp_estimate = (best_power * PCT_20MIN_FACTOR).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )

    log.info(
        "threshold_estimated",
        best_20min=str(best_power),
        ftp_estimate=str(ftp_estimate),
        source_activity_id=activity_id,
    )

    # Check for existing threshold of same method/date
    existing_stmt = select(Threshold).where(
        Threshold.user_id == user_id,
        Threshold.method == "pct_20min",
        Threshold.effective_date == activity_date,
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        existing.ftp_watts = ftp_estimate
        existing.source_activity_id = activity_id
        existing.is_active = True
        return existing

    threshold = Threshold(
        user_id=user_id,
        method="pct_20min",
        effective_date=activity_date,
        ftp_watts=ftp_estimate,
        source_activity_id=activity_id,
        is_active=True,
        notes=f"Auto-detected: 95% of {best_power}W best 20-min effort",
    )
    db.add(threshold)
    return threshold


async def estimate_threshold_8min(
    user_id: int,
    db: AsyncSession,
) -> Threshold | None:
    """Estimate FTP as 90% of the best 8-minute power effort.

    Same approach as 20-minute estimation but with a shorter window
    and a more conservative scaling factor (0.90 vs 0.95).

    Returns:
        A new (uncommitted) Threshold record, or None if no qualifying rides.
    """
    log = logger.bind(user_id=user_id, method="pct_8min")

    result = await _find_best_effort_across_activities(
        user_id, EIGHT_MIN_SECONDS, db
    )

    if result is None:
        log.info("no_qualifying_rides", min_duration=EIGHT_MIN_SECONDS)
        return None

    best_power, activity_id, activity_date = result
    ftp_estimate = (best_power * PCT_8MIN_FACTOR).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )

    log.info(
        "threshold_estimated",
        best_8min=str(best_power),
        ftp_estimate=str(ftp_estimate),
        source_activity_id=activity_id,
    )

    # Check for existing threshold of same method/date
    existing_stmt = select(Threshold).where(
        Threshold.user_id == user_id,
        Threshold.method == "pct_8min",
        Threshold.effective_date == activity_date,
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        existing.ftp_watts = ftp_estimate
        existing.source_activity_id = activity_id
        existing.is_active = True
        return existing

    threshold = Threshold(
        user_id=user_id,
        method="pct_8min",
        effective_date=activity_date,
        ftp_watts=ftp_estimate,
        source_activity_id=activity_id,
        is_active=True,
        notes=f"Auto-detected: 90% of {best_power}W best 8-min effort",
    )
    db.add(threshold)
    return threshold


async def get_threshold_at_date(
    user_id: int,
    method: str,
    target_date: date,
    db: AsyncSession,
) -> Threshold | None:
    """Look up the most recent active threshold before or on the given date.

    This enables historical threshold lookup for accurate retrospective analysis.

    Args:
        user_id: The user to look up.
        method: Threshold method (manual, pct_20min, pct_8min).
        target_date: The date to look up the threshold for.
        db: Async database session.

    Returns:
        The most recent Threshold before target_date, or None.
    """
    stmt = (
        select(Threshold)
        .where(
            Threshold.user_id == user_id,
            Threshold.method == method,
            Threshold.is_active.is_(True),
            Threshold.effective_date <= target_date,
        )
        .order_by(Threshold.effective_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
