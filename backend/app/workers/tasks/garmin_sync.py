"""Celery tasks for Garmin Connect sync — activities and health data.

Runs in Celery worker context with SYNC database access (psycopg2).
Downloads FIT files from Garmin and pipes them through the existing import pipeline.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select, update

from app.config import get_settings
from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.health_metric import HealthMetric, MetricType
from app.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.services.garmin_service import (
    GarminAuthError,
    GarminService,
    GarminSyncError,
    decrypt_credentials,
)
from app.services.storage_service import save_fit_file
from app.workers.base_task import BaseTask
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Default lookback: 30 days if no last_sync_at is set
DEFAULT_LOOKBACK_DAYS = 30


def _get_garmin_service(session: Any, user_id: int) -> tuple[GarminService, Integration]:
    """Load encrypted credentials from DB, decrypt, and create an authenticated GarminService.

    Args:
        session: Sync SQLAlchemy session.
        user_id: User ID to load integration for.

    Returns:
        Tuple of (authenticated GarminService, Integration record).

    Raises:
        GarminAuthError: If no integration found or credentials invalid.
        GarminSyncError: If login fails.
    """
    settings = get_settings()

    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == IntegrationProvider.garmin,
    )
    integration = session.execute(stmt).scalar_one_or_none()

    if integration is None:
        raise GarminAuthError("No Garmin integration found for user")

    if integration.credentials_encrypted is None:
        raise GarminAuthError("Garmin credentials not configured")

    email, password = decrypt_credentials(integration.credentials_encrypted, settings.SECRET_KEY)
    svc = GarminService(email, password)
    svc.login()

    return svc, integration


def _update_integration_error(
    session: Any,
    user_id: int,
    error_msg: str,
) -> None:
    """Mark the Garmin integration as errored."""
    try:
        session.execute(
            update(Integration)
            .where(
                Integration.user_id == user_id,
                Integration.provider == IntegrationProvider.garmin,
            )
            .values(
                status=IntegrationStatus.error,
                error_message=error_msg[:1000],
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("failed_to_update_integration_error_status")


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.garmin_sync.sync_garmin_activities",
    queue="low_priority",
)
def sync_garmin_activities(self: BaseTask, user_id: int) -> dict[str, Any]:
    """Fetch new activities from Garmin Connect and import their FIT files.

    1. Authenticate with Garmin Connect using stored credentials.
    2. Fetch activities since last_sync_at (or DEFAULT_LOOKBACK_DAYS ago).
    3. For each new activity, download the FIT file.
    4. Save through the existing storage pipeline.
    5. Create Activity records and queue FIT parsing tasks.
    6. Update last_sync_at on the integration.

    Args:
        user_id: User ID to sync activities for.

    Returns:
        Dict with synced_count, skipped_count, and error_count.
    """
    log = logger.bind(user_id=user_id, task="sync_garmin_activities")
    log.info("garmin_activity_sync_started")

    session = self.session_maker()
    try:
        svc, integration = _get_garmin_service(session, user_id)

        # Determine sync window
        if integration.last_sync_at is not None:
            since = integration.last_sync_at
        else:
            since = datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)

        # Fetch activities from Garmin
        garmin_activities = svc.get_activities(since)
        log.info("garmin_activities_found", count=len(garmin_activities))

        synced = 0
        skipped = 0
        errors = 0

        for i, garmin_act in enumerate(garmin_activities):
            garmin_id = str(garmin_act.get("activityId", ""))
            act_name = garmin_act.get("activityName", "Garmin Activity")

            try:
                # Check if already imported (by external_id)
                existing_stmt = select(Activity).where(
                    Activity.user_id == user_id,
                    Activity.external_id == garmin_id,
                )
                existing = session.execute(existing_stmt).scalar_one_or_none()

                if existing is not None:
                    log.debug("garmin_activity_already_imported", garmin_id=garmin_id)
                    skipped += 1
                    continue

                # Download FIT file
                fit_content = svc.download_fit(garmin_id)
                if not fit_content:
                    log.warning("garmin_fit_empty", garmin_id=garmin_id)
                    skipped += 1
                    continue

                # Check for duplicate by file hash
                file_hash = hashlib.sha256(fit_content).hexdigest()
                hash_stmt = select(Activity).where(
                    Activity.user_id == user_id,
                    Activity.file_hash == file_hash,
                )
                hash_existing = session.execute(hash_stmt).scalar_one_or_none()

                if hash_existing is not None:
                    log.debug("garmin_fit_hash_duplicate", garmin_id=garmin_id)
                    skipped += 1
                    continue

                # Save FIT file to disk
                file_path = save_fit_file(fit_content, user_id)

                # Parse activity date from Garmin data
                start_time_str = garmin_act.get("startTimeLocal") or garmin_act.get(
                    "startTimeGMT", ""
                )
                try:
                    activity_date = datetime.fromisoformat(str(start_time_str))
                except (ValueError, TypeError):
                    activity_date = datetime.now(UTC)

                # Create Activity record
                activity = Activity(
                    user_id=user_id,
                    external_id=garmin_id,
                    source=ActivitySource.garmin,
                    activity_date=activity_date,
                    name=act_name,
                    processing_status=ProcessingStatus.pending,
                    fit_file_path=file_path,
                    file_hash=file_hash,
                )
                session.add(activity)
                session.flush()

                # Queue FIT parsing on high_priority queue
                celery_app.send_task(
                    "app.workers.tasks.fit_import.process_fit_upload",
                    args=[activity.id, file_path],
                    queue="high_priority",
                )

                log.info(
                    "garmin_activity_synced",
                    garmin_id=garmin_id,
                    activity_id=activity.id,
                )
                synced += 1

            except Exception as exc:
                log.exception(
                    "garmin_activity_sync_error",
                    garmin_id=garmin_id,
                    error=str(exc),
                )
                errors += 1

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": int((i + 1) * 100 / len(garmin_activities)),
                    "total": 100,
                    "stage": f"Syncing activity {i + 1}/{len(garmin_activities)}",
                },
            )

        # Update last_sync_at
        session.execute(
            update(Integration)
            .where(Integration.id == integration.id)
            .values(
                last_sync_at=datetime.now(UTC),
                status=IntegrationStatus.active,
                error_message=None,
            )
        )
        session.commit()

        result = {
            "synced_count": synced,
            "skipped_count": skipped,
            "error_count": errors,
        }
        log.info("garmin_activity_sync_complete", **result)
        return result

    except (GarminAuthError, GarminSyncError) as exc:
        session.rollback()
        log.exception("garmin_activity_sync_failed", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    except Exception as exc:
        session.rollback()
        log.exception("garmin_activity_sync_unexpected_error", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    finally:
        session.close()


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.garmin_sync.sync_garmin_health",
    queue="low_priority",
)
def sync_garmin_health(self: BaseTask, user_id: int) -> dict[str, Any]:
    """Fetch health/wellness metrics from Garmin Connect and store in health_metrics.

    Retrieves today's data for: sleep_score, weight_kg, resting_hr, hrv_ms,
    body_battery, stress_avg.

    Args:
        user_id: User ID to sync health data for.

    Returns:
        Dict with metrics_saved count.
    """
    log = logger.bind(user_id=user_id, task="sync_garmin_health")
    log.info("garmin_health_sync_started")

    session = self.session_maker()
    try:
        svc, integration = _get_garmin_service(session, user_id)

        today = date.today()
        health_data = svc.get_health_data(today)

        metrics_saved = 0
        metric_type_map: dict[str, MetricType] = {
            "sleep_score": MetricType.sleep_score,
            "weight_kg": MetricType.weight_kg,
            "resting_hr": MetricType.resting_hr,
            "hrv_ms": MetricType.hrv_ms,
            "body_battery": MetricType.body_battery,
            "stress_avg": MetricType.stress_avg,
        }

        for key, metric_type in metric_type_map.items():
            value = health_data.get(key)
            if value is None:
                continue

            # Check if metric already exists for this date
            existing_stmt = select(HealthMetric).where(
                HealthMetric.user_id == user_id,
                HealthMetric.date == today,
                HealthMetric.metric_type == metric_type,
            )
            existing = session.execute(existing_stmt).scalar_one_or_none()

            if existing is not None:
                # Update existing value
                existing.value = value
                existing.source = "garmin"
                log.debug("garmin_health_metric_updated", metric=key, value=str(value))
            else:
                # Create new metric
                metric = HealthMetric(
                    user_id=user_id,
                    date=today,
                    metric_type=metric_type,
                    value=value,
                    source="garmin",
                )
                session.add(metric)
                log.debug("garmin_health_metric_created", metric=key, value=str(value))

            metrics_saved += 1

        # Update last_sync_at
        session.execute(
            update(Integration)
            .where(Integration.id == integration.id)
            .values(
                last_sync_at=datetime.now(UTC),
                status=IntegrationStatus.active,
                error_message=None,
            )
        )
        session.commit()

        result = {"metrics_saved": metrics_saved}
        log.info("garmin_health_sync_complete", **result)
        return result

    except (GarminAuthError, GarminSyncError) as exc:
        session.rollback()
        log.exception("garmin_health_sync_failed", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    except Exception as exc:
        session.rollback()
        log.exception("garmin_health_sync_unexpected_error", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    finally:
        session.close()
