"""Metric computation service — calculates Coggan metrics for activities.

Computes NP, IF, TSS, zone distribution, variability index, and
efficiency factor from activity stream data. Results are stored in
the activity_metrics table and summary fields on the activity itself.
"""

from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_metrics import ActivityMetrics
from app.models.activity_stream import ActivityStream
from app.models.user_settings import UserSettings
from app.utils.coggan_model import (
    calculate_intensity_factor,
    calculate_normalized_power,
    calculate_tss,
    calculate_zone_distribution,
    estimate_tss_from_avg_power,
)

logger = structlog.get_logger(__name__)

DEFAULT_FTP = Decimal("200")


async def compute_activity_metrics(
    activity_id: int,
    user_id: int,
    db: AsyncSession,
    threshold_method: str = "manual",
) -> ActivityMetrics:
    """Compute and store Coggan metrics for a single activity.

    Steps:
        1. Fetch activity from DB
        2. Fetch user FTP (default 200 if not set)
        3. Fetch power stream data
        4. Calculate NP, IF, TSS, zone distribution, VI, EF
        5. Upsert into activity_metrics
        6. Update activity summary fields

    Returns:
        The created/updated ActivityMetrics record.
    """
    log = logger.bind(activity_id=activity_id, user_id=user_id)

    # 1. Fetch activity
    stmt = select(Activity).where(Activity.id == activity_id, Activity.user_id == user_id)
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()
    if activity is None:
        raise ValueError(f"Activity {activity_id} not found for user {user_id}")

    # 2. Fetch user FTP
    settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
    settings_result = await db.execute(settings_stmt)
    user_settings = settings_result.scalar_one_or_none()
    ftp = (
        user_settings.ftp_watts
        if user_settings and user_settings.ftp_watts
        else DEFAULT_FTP
    )

    log.info("computing_metrics", ftp=str(ftp), threshold_method=threshold_method)

    # 3. Fetch power stream data
    stream_stmt = (
        select(ActivityStream.power_watts, ActivityStream.heart_rate)
        .where(ActivityStream.activity_id == activity_id)
        .order_by(ActivityStream.timestamp)
    )
    stream_result = await db.execute(stream_stmt)
    stream_rows = stream_result.fetchall()

    power_data: list[int | None] = [row.power_watts for row in stream_rows]
    hr_data: list[int | None] = [row.heart_rate for row in stream_rows]

    # 4. Calculate metrics
    np_result = None
    np_watts: Decimal | None = None
    avg_power: Decimal | None = None
    if_value: Decimal | None = None
    tss_value: Decimal | None = None
    zone_dist_dict: dict | None = None
    variability_index: Decimal | None = None
    efficiency_factor: Decimal | None = None

    has_stream_data = len(power_data) > 0 and any(p is not None for p in power_data)

    if has_stream_data:
        # Full computation from stream data
        np_result = calculate_normalized_power(power_data)
        np_watts = np_result.np_watts
        avg_power = np_result.avg_power

        if np_watts is not None and np_watts > 0:
            if_value = calculate_intensity_factor(np_watts, ftp)
            tss_value = calculate_tss(
                duration_seconds=activity.duration_seconds or 0,
                np_watts=np_watts,
                if_value=if_value,
                ftp_watts=ftp,
            )

        # Zone distribution
        ftp_int = int(ftp)
        if ftp_int > 0:
            zone_result = calculate_zone_distribution(power_data, ftp_int)
            zone_dist_dict = {
                "zone_seconds": zone_result.zone_seconds,
                "total_seconds": zone_result.total_seconds,
            }

        # Variability index: NP / avg_power
        if np_watts is not None and avg_power is not None and avg_power > 0:
            vi = np_watts / avg_power
            variability_index = vi.quantize(Decimal("0.01"))

        # Efficiency factor: NP / avg_HR (if HR data available)
        valid_hr = [h for h in hr_data if h is not None and h > 0]
        if np_watts is not None and valid_hr:
            avg_hr = Decimal(str(sum(valid_hr))) / Decimal(str(len(valid_hr)))
            if avg_hr > 0:
                ef = np_watts / avg_hr
                efficiency_factor = ef.quantize(Decimal("0.01"))

    elif activity.avg_power_watts is not None and activity.avg_power_watts > 0:
        # Manual activity — estimate from avg_power
        avg_power = activity.avg_power_watts
        np_watts = avg_power  # best estimate without stream data
        if_value = calculate_intensity_factor(avg_power, ftp)
        tss_value = estimate_tss_from_avg_power(
            duration_seconds=activity.duration_seconds or 0,
            avg_power=avg_power,
            ftp_watts=ftp,
        )
        variability_index = Decimal("1.00")  # no variability for avg-only

    # 5. Upsert into activity_metrics
    existing_stmt = select(ActivityMetrics).where(
        ActivityMetrics.activity_id == activity_id,
        ActivityMetrics.threshold_method == threshold_method,
    )
    existing_result = await db.execute(existing_stmt)
    metrics = existing_result.scalar_one_or_none()

    if metrics is None:
        metrics = ActivityMetrics(
            activity_id=activity_id,
            user_id=user_id,
            threshold_method=threshold_method,
        )
        db.add(metrics)

    metrics.ftp_at_computation = ftp
    metrics.normalized_power = np_watts
    metrics.tss = tss_value
    metrics.intensity_factor = if_value
    metrics.zone_distribution = zone_dist_dict
    metrics.variability_index = variability_index
    metrics.efficiency_factor = efficiency_factor

    await db.flush()

    # 6. Update activity summary fields
    await db.execute(
        update(Activity)
        .where(Activity.id == activity_id)
        .values(
            tss=tss_value,
            np_watts=np_watts,
            intensity_factor=if_value,
        )
    )
    await db.flush()

    log.info(
        "metrics_computed",
        np=str(np_watts),
        tss=str(tss_value),
        if_value=str(if_value),
    )

    return metrics


async def recompute_all_metrics(
    user_id: int,
    db: AsyncSession,
    threshold_method: str = "manual",
) -> int:
    """Recompute metrics for all activities belonging to a user.

    Returns:
        Number of activities recomputed.
    """
    stmt = select(Activity.id).where(Activity.user_id == user_id)
    result = await db.execute(stmt)
    activity_ids = [row[0] for row in result.fetchall()]

    count = 0
    for aid in activity_ids:
        try:
            await compute_activity_metrics(aid, user_id, db, threshold_method)
            count += 1
        except Exception:
            logger.exception("recompute_failed", activity_id=aid)

    logger.info("recompute_all_complete", user_id=user_id, count=count)
    return count
