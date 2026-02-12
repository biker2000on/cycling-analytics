"""Celery tasks for metric computation and fitness updates.

Runs in Celery worker context with SYNC database access (psycopg2).
Computes Coggan metrics for individual activities and triggers
fitness history updates.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select, update

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
from app.workers.base_task import BaseTask
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

DEFAULT_FTP = Decimal("200")


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.metric_computation.compute_activity_metrics_task",
)
def compute_activity_metrics_task(self: BaseTask, activity_id: int) -> dict[str, Any]:
    """Compute Coggan metrics for a single activity (sync/Celery context).

    Args:
        activity_id: Database ID of the Activity record.

    Returns:
        Dict with activity_id, np, tss, if_value.
    """
    log = logger.bind(activity_id=activity_id)
    log.info("metric_computation_started")

    session = self.session_maker()
    try:
        # Fetch activity
        activity = session.execute(
            select(Activity).where(Activity.id == activity_id)
        ).scalar_one_or_none()

        if activity is None:
            raise ValueError(f"Activity {activity_id} not found")

        user_id = activity.user_id

        # Fetch FTP
        user_settings = session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        ).scalar_one_or_none()

        ftp = (
            user_settings.ftp_watts
            if user_settings and user_settings.ftp_watts
            else DEFAULT_FTP
        )

        # Fetch power stream data
        stream_rows = session.execute(
            select(ActivityStream.power_watts, ActivityStream.heart_rate)
            .where(ActivityStream.activity_id == activity_id)
            .order_by(ActivityStream.timestamp)
        ).fetchall()

        power_data: list[int | None] = [row.power_watts for row in stream_rows]
        hr_data: list[int | None] = [row.heart_rate for row in stream_rows]

        # Calculate metrics
        np_watts: Decimal | None = None
        avg_power: Decimal | None = None
        if_value: Decimal | None = None
        tss_value: Decimal | None = None
        zone_dist_dict: dict | None = None
        variability_index: Decimal | None = None
        efficiency_factor: Decimal | None = None

        has_stream_data = len(power_data) > 0 and any(p is not None for p in power_data)

        if has_stream_data:
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

            ftp_int = int(ftp)
            if ftp_int > 0:
                zone_result = calculate_zone_distribution(power_data, ftp_int)
                zone_dist_dict = {
                    "zone_seconds": zone_result.zone_seconds,
                    "total_seconds": zone_result.total_seconds,
                }

            if np_watts is not None and avg_power is not None and avg_power > 0:
                vi = np_watts / avg_power
                variability_index = vi.quantize(Decimal("0.01"))

            valid_hr = [h for h in hr_data if h is not None and h > 0]
            if np_watts is not None and valid_hr:
                avg_hr = Decimal(str(sum(valid_hr))) / Decimal(str(len(valid_hr)))
                if avg_hr > 0:
                    ef = np_watts / avg_hr
                    efficiency_factor = ef.quantize(Decimal("0.01"))

        elif activity.avg_power_watts is not None and activity.avg_power_watts > 0:
            avg_power = activity.avg_power_watts
            np_watts = avg_power
            if_value = calculate_intensity_factor(avg_power, ftp)
            tss_value = estimate_tss_from_avg_power(
                duration_seconds=activity.duration_seconds or 0,
                avg_power=avg_power,
                ftp_watts=ftp,
            )
            variability_index = Decimal("1.00")

        # Upsert activity_metrics
        existing = session.execute(
            select(ActivityMetrics).where(
                ActivityMetrics.activity_id == activity_id,
                ActivityMetrics.threshold_method == "manual",
            )
        ).scalar_one_or_none()

        if existing is None:
            metrics = ActivityMetrics(
                activity_id=activity_id,
                user_id=user_id,
                threshold_method="manual",
            )
            session.add(metrics)
        else:
            metrics = existing

        metrics.ftp_at_computation = ftp
        metrics.normalized_power = np_watts
        metrics.tss = tss_value
        metrics.intensity_factor = if_value
        metrics.zone_distribution = zone_dist_dict
        metrics.variability_index = variability_index
        metrics.efficiency_factor = efficiency_factor

        # Update activity summary fields
        session.execute(
            update(Activity)
            .where(Activity.id == activity_id)
            .values(
                tss=tss_value,
                np_watts=np_watts,
                intensity_factor=if_value,
            )
        )

        session.commit()

        log.info(
            "metric_computation_complete",
            np=str(np_watts),
            tss=str(tss_value),
            if_value=str(if_value),
        )

        # Trigger fitness update (log for now; will be chained in Phase 2.4+)
        log.info("fitness_update_trigger", activity_id=activity_id, user_id=user_id)

        return {
            "activity_id": activity_id,
            "np": str(np_watts) if np_watts else None,
            "tss": str(tss_value) if tss_value else None,
            "if_value": str(if_value) if if_value else None,
        }

    except Exception as exc:
        session.rollback()
        log.exception("metric_computation_failed", error=str(exc))
        raise
    finally:
        session.close()


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.metric_computation.recompute_all_metrics_task",
    queue="low_priority",
)
def recompute_all_metrics_task(self: BaseTask, user_id: int) -> dict[str, Any]:
    """Recompute metrics for all activities of a user (low priority).

    Args:
        user_id: User ID to recompute for.

    Returns:
        Dict with user_id and count of activities recomputed.
    """
    log = logger.bind(user_id=user_id)
    log.info("recompute_all_started")

    session = self.session_maker()
    try:
        activity_ids = [
            row[0]
            for row in session.execute(
                select(Activity.id).where(Activity.user_id == user_id)
            ).fetchall()
        ]

        count = 0
        for aid in activity_ids:
            try:
                # Reuse the sync task logic inline
                compute_activity_metrics_task(aid)
                count += 1
            except Exception:
                log.exception("recompute_single_failed", activity_id=aid)

        log.info("recompute_all_complete", count=count)
        return {"user_id": user_id, "count": count}

    finally:
        session.close()
