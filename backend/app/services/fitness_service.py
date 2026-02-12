"""Fitness tracking service — CTL/ATL/TSB daily updates.

Aggregates daily TSS from activity_metrics and computes chronic/acute
training load using Coggan's EWMA model.
"""

from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_metrics import ActivityMetrics
from app.models.fitness_metrics import DailyFitness
from app.utils.coggan_model import calculate_ctl_atl_tsb

logger = structlog.get_logger(__name__)


async def update_fitness_from_date(
    user_id: int,
    from_date: date,
    db: AsyncSession,
    threshold_method: str = "manual",
) -> int:
    """Update daily fitness (CTL/ATL/TSB) from a given date to today.

    Steps:
        1. Get previous day's CTL/ATL from daily_fitness (or 0 if first entry)
        2. Get daily TSS totals from activity_metrics for this user
        3. Calculate CTL/ATL/TSB using coggan_model
        4. Upsert daily_fitness rows for each day
        5. Return number of days updated

    Args:
        user_id: The user to update fitness for.
        from_date: Start date for the update window.
        db: Async database session.
        threshold_method: Threshold method (default 'manual').

    Returns:
        Number of days updated.
    """
    log = logger.bind(user_id=user_id, from_date=str(from_date))
    today = date.today()

    if from_date > today:
        return 0

    # 1. Get previous day's CTL/ATL
    prev_date = from_date - timedelta(days=1)
    prev_stmt = select(DailyFitness).where(
        DailyFitness.user_id == user_id,
        DailyFitness.date == prev_date,
        DailyFitness.threshold_method == threshold_method,
    )
    prev_result = await db.execute(prev_stmt)
    prev_fitness = prev_result.scalar_one_or_none()

    initial_ctl = prev_fitness.ctl if prev_fitness else Decimal("0")
    initial_atl = prev_fitness.atl if prev_fitness else Decimal("0")

    # 2. Get daily TSS totals from activity_metrics
    tss_stmt = (
        select(
            func.cast(Activity.activity_date, type_=func.date().type).label("activity_day"),
            func.sum(ActivityMetrics.tss).label("tss_total"),
            func.count(ActivityMetrics.id).label("activity_count"),
        )
        .join(Activity, ActivityMetrics.activity_id == Activity.id)
        .where(
            ActivityMetrics.user_id == user_id,
            ActivityMetrics.threshold_method == threshold_method,
            ActivityMetrics.tss.is_not(None),
            Activity.activity_date >= from_date,
            Activity.activity_date <= today,
        )
        .group_by("activity_day")
    )
    tss_result = await db.execute(tss_stmt)
    tss_rows = tss_result.fetchall()

    # Build daily TSS list covering from_date to today
    tss_map: dict[date, tuple[Decimal, int]] = {}
    for row in tss_rows:
        # activity_day may come back as datetime or date depending on DB
        day = row.activity_day
        if hasattr(day, "date"):
            day = day.date()
        tss_map[day] = (Decimal(str(row.tss_total)), int(row.activity_count))

    # Build daily_tss list for every day in range (rest days get TSS=0)
    daily_tss: list[tuple[date, Decimal]] = []
    current = from_date
    while current <= today:
        tss_val = tss_map.get(current, (Decimal("0"), 0))[0]
        daily_tss.append((current, tss_val))
        current += timedelta(days=1)

    # 3. Calculate CTL/ATL/TSB
    fitness_points = calculate_ctl_atl_tsb(daily_tss, initial_ctl, initial_atl)

    # 4. Upsert daily_fitness rows
    count = 0
    for point in fitness_points:
        activity_count = tss_map.get(point.date, (Decimal("0"), 0))[1]

        existing_stmt = select(DailyFitness).where(
            DailyFitness.user_id == user_id,
            DailyFitness.date == point.date,
            DailyFitness.threshold_method == threshold_method,
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing is None:
            row = DailyFitness(
                user_id=user_id,
                date=point.date,
                threshold_method=threshold_method,
                tss_total=point.tss_total,
                activity_count=activity_count,
                ctl=point.ctl,
                atl=point.atl,
                tsb=point.tsb,
            )
            db.add(row)
        else:
            existing.tss_total = point.tss_total
            existing.activity_count = activity_count
            existing.ctl = point.ctl
            existing.atl = point.atl
            existing.tsb = point.tsb

        count += 1

    await db.flush()

    log.info("fitness_updated", days=count)
    return count


async def rebuild_fitness_history(
    user_id: int,
    db: AsyncSession,
    threshold_method: str = "manual",
) -> int:
    """Full rebuild of fitness history from the user's first activity to today.

    Deletes existing daily_fitness rows for the user/method and rebuilds
    from scratch using all activity_metrics data.

    Returns:
        Number of days computed.
    """
    log = logger.bind(user_id=user_id, threshold_method=threshold_method)

    # Find earliest activity date
    earliest_stmt = (
        select(func.min(Activity.activity_date))
        .where(Activity.user_id == user_id)
    )
    earliest_result = await db.execute(earliest_stmt)
    earliest = earliest_result.scalar_one_or_none()

    if earliest is None:
        log.info("no_activities_for_rebuild")
        return 0

    # Convert to date if datetime
    first_date = earliest.date() if hasattr(earliest, "date") else earliest

    # Delete existing fitness rows for this user/method
    await db.execute(
        delete(DailyFitness).where(
            and_(
                DailyFitness.user_id == user_id,
                DailyFitness.threshold_method == threshold_method,
            )
        )
    )
    await db.flush()

    # Rebuild from first activity date
    return await update_fitness_from_date(user_id, first_date, db, threshold_method)
