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
from app.models.threshold import Threshold
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

    # 2. Fetch user FTP — resolve per threshold method
    if threshold_method == "manual":
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings_result = await db.execute(settings_stmt)
        user_settings = settings_result.scalar_one_or_none()
        ftp = (
            user_settings.ftp_watts
            if user_settings and user_settings.ftp_watts
            else DEFAULT_FTP
        )
    else:
        # For auto-detected methods, look up threshold at the activity date
        from app.services.threshold_service import get_threshold_at_date

        target_date = activity.activity_date
        if hasattr(target_date, "date"):
            target_date = target_date.date()
        threshold_record = await get_threshold_at_date(
            user_id, threshold_method, target_date, db
        )
        if threshold_record is not None:
            ftp = threshold_record.ftp_watts
        else:
            # Fall back to user settings FTP for non-manual methods without a threshold
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


async def _get_ftp_for_method(
    user_id: int,
    method: str,
    activity_date,
    db: AsyncSession,
) -> Decimal | None:
    """Resolve the FTP value for a given threshold method and date.

    For 'manual', uses user_settings.ftp_watts.
    For auto-detected methods, looks up the most recent threshold
    at or before the activity date.

    Returns:
        The FTP value, or None if no threshold is available for this method.
    """
    if method == "manual":
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        settings_result = await db.execute(settings_stmt)
        user_settings = settings_result.scalar_one_or_none()
        if user_settings and user_settings.ftp_watts:
            return user_settings.ftp_watts
        return DEFAULT_FTP

    # For auto-detected methods, look up the threshold table
    from app.services.threshold_service import get_threshold_at_date

    # Convert activity_date to date if it's datetime
    target_date = activity_date
    if hasattr(target_date, "date"):
        target_date = target_date.date()

    threshold = await get_threshold_at_date(user_id, method, target_date, db)
    if threshold is not None:
        return threshold.ftp_watts
    return None


async def compute_activity_metrics_all_methods(
    activity_id: int,
    user_id: int,
    db: AsyncSession,
) -> list[ActivityMetrics]:
    """Compute and store metrics for ALL available threshold methods.

    For each method that has a threshold available, computes NP/IF/TSS/zones
    and stores separate activity_metrics rows per method.

    Args:
        activity_id: The activity to compute metrics for.
        user_id: The user who owns the activity.
        db: Async database session.

    Returns:
        List of ActivityMetrics records (one per method with available threshold).
    """
    log = logger.bind(activity_id=activity_id, user_id=user_id)

    # 1. Fetch the activity to get its date
    activity_stmt = select(Activity).where(
        Activity.id == activity_id, Activity.user_id == user_id
    )
    activity_result = await db.execute(activity_stmt)
    activity = activity_result.scalar_one_or_none()
    if activity is None:
        raise ValueError(f"Activity {activity_id} not found for user {user_id}")

    # 2. Determine which methods have available thresholds
    methods_to_compute: list[str] = []

    # Manual always available (uses user_settings.ftp_watts or default)
    methods_to_compute.append("manual")

    # Check auto-detected methods
    for method in ("pct_20min", "pct_8min"):
        ftp = await _get_ftp_for_method(user_id, method, activity.activity_date, db)
        if ftp is not None:
            methods_to_compute.append(method)

    log.info("computing_all_methods", methods=methods_to_compute)

    # 3. Compute metrics for each method
    results: list[ActivityMetrics] = []
    for method in methods_to_compute:
        try:
            metrics = await compute_activity_metrics(
                activity_id, user_id, db, threshold_method=method
            )
            results.append(metrics)
        except Exception:
            log.exception("multi_method_compute_failed", method=method)

    return results
