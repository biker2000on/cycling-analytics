"""Celery tasks for Strava sync — activity import, webhooks, and backfill.

Runs in Celery worker context with SYNC database access (psycopg2).
Fetches activities from Strava API and stores them through the internal pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, update

from app.config import get_settings
from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.models.activity_stream import ActivityStream
from app.services.strava_rate_limiter import StravaRateLimiter
from app.services.strava_service import (
    StravaAuthError,
    StravaService,
    StravaSyncError,
    decrypt_token,
    encrypt_token,
)
from app.workers.base_task import BaseTask
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Default lookback: 30 days if no last_sync_at
DEFAULT_LOOKBACK_DAYS = 30

# Shared rate limiter instance (per-worker process)
_rate_limiter = StravaRateLimiter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_strava_integration(session: Any, user_id: int) -> Integration:
    """Load the Strava integration record for a user.

    Raises:
        StravaAuthError: If no integration found or disconnected.
    """
    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == IntegrationProvider.strava,
    )
    integration = session.execute(stmt).scalar_one_or_none()

    if integration is None:
        raise StravaAuthError("No Strava integration found for user")

    if integration.status == IntegrationStatus.disconnected:
        raise StravaAuthError("Strava integration is disconnected")

    return integration


def _get_valid_access_token(session: Any, integration: Integration) -> str:
    """Get a valid access token, refreshing if expired.

    Updates the integration record in-place if tokens are refreshed.

    Returns:
        Valid access token string.

    Raises:
        StravaAuthError: If tokens cannot be decrypted or refreshed.
    """
    settings = get_settings()

    if integration.access_token_encrypted is None:
        raise StravaAuthError("Strava access token not configured")

    if integration.refresh_token_encrypted is None:
        raise StravaAuthError("Strava refresh token not configured")

    access_token = decrypt_token(integration.access_token_encrypted, settings.SECRET_KEY)

    # Check if token is expired or expiring soon (5 min buffer)
    if integration.token_expires_at is not None:
        now = datetime.now(UTC)
        if now >= (integration.token_expires_at - timedelta(minutes=5)):
            logger.info("strava_token_expired_refreshing")
            refresh_token = decrypt_token(
                integration.refresh_token_encrypted, settings.SECRET_KEY
            )

            svc = StravaService()
            try:
                token_data = svc.refresh_tokens(refresh_token)
            finally:
                svc.close()

            new_access = token_data["access_token"]
            new_refresh = token_data.get("refresh_token", refresh_token)
            expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=UTC)

            integration.access_token_encrypted = encrypt_token(
                new_access, settings.SECRET_KEY
            )
            integration.refresh_token_encrypted = encrypt_token(
                new_refresh, settings.SECRET_KEY
            )
            integration.token_expires_at = expires_at
            session.flush()

            access_token = new_access

    return access_token


def _update_integration_error(
    session: Any,
    user_id: int,
    error_msg: str,
) -> None:
    """Mark the Strava integration as errored."""
    try:
        session.execute(
            update(Integration)
            .where(
                Integration.user_id == user_id,
                Integration.provider == IntegrationProvider.strava,
            )
            .values(
                status=IntegrationStatus.error,
                error_message=error_msg[:1000],
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("failed_to_update_strava_integration_error_status")


def _import_strava_activity(
    session: Any,
    svc: StravaService,
    access_token: str,
    strava_activity: dict[str, Any],
    user_id: int,
) -> str:
    """Import a single Strava activity into the database.

    Args:
        session: Sync DB session.
        svc: StravaService instance.
        access_token: Valid Strava access token.
        strava_activity: Activity summary dict from Strava.
        user_id: Internal user ID.

    Returns:
        "synced", "skipped", or "error".
    """
    strava_id = str(strava_activity.get("id", ""))

    # Check if already imported
    existing_stmt = select(Activity).where(
        Activity.user_id == user_id,
        Activity.external_id == strava_id,
        Activity.source == ActivitySource.strava,
    )
    existing = session.execute(existing_stmt).scalar_one_or_none()
    if existing is not None:
        return "skipped"

    try:
        # Fetch full detail and streams
        _rate_limiter.wait_if_needed()
        detail = svc.fetch_activity_detail(access_token, int(strava_id))
        _rate_limiter.record_request()

        _rate_limiter.wait_if_needed()
        streams_data = svc.fetch_activity_streams(access_token, int(strava_id))
        _rate_limiter.record_request()

        # Convert to internal format
        activity_data, stream_records = StravaService.convert_strava_to_internal(
            detail, streams_data
        )

        # Create Activity record
        activity = Activity(
            user_id=user_id,
            external_id=strava_id,
            source=ActivitySource.strava,
            activity_date=activity_data["activity_date"],
            name=activity_data["name"],
            sport_type=activity_data.get("sport_type"),
            duration_seconds=activity_data.get("duration_seconds"),
            distance_meters=activity_data.get("distance_meters"),
            elevation_gain_meters=activity_data.get("elevation_gain_meters"),
            avg_power_watts=activity_data.get("avg_power_watts"),
            max_power_watts=activity_data.get("max_power_watts"),
            avg_hr=activity_data.get("avg_hr"),
            max_hr=activity_data.get("max_hr"),
            avg_cadence=activity_data.get("avg_cadence"),
            calories=activity_data.get("calories"),
            device_name=activity_data.get("device_name"),
            processing_status=ProcessingStatus.complete,
        )
        session.add(activity)
        session.flush()

        # Insert stream records
        for rec in stream_records:
            stream = ActivityStream(
                activity_id=activity.id,
                timestamp=rec["timestamp"],
                elapsed_seconds=rec.get("elapsed_seconds"),
                power_watts=rec.get("power_watts"),
                heart_rate=rec.get("heart_rate"),
                cadence=rec.get("cadence"),
                altitude_meters=rec.get("altitude_meters"),
                distance_meters=rec.get("distance_meters"),
                position=rec.get("position"),
            )
            session.add(stream)

        # Queue metric computation
        celery_app.send_task(
            "app.workers.tasks.metric_computation.compute_activity_metrics_task",
            args=[activity.id],
            queue="high_priority",
        )

        logger.info(
            "strava_activity_imported",
            strava_id=strava_id,
            activity_id=activity.id,
            streams=len(stream_records),
        )
        return "synced"

    except Exception as exc:
        logger.exception(
            "strava_activity_import_error",
            strava_id=strava_id,
            error=str(exc),
        )
        return "error"


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.strava_sync.sync_strava_activities",
    queue="low_priority",
)
def sync_strava_activities(self: BaseTask, user_id: int) -> dict[str, Any]:
    """Incremental sync of Strava activities since last sync.

    Args:
        user_id: User ID to sync for.

    Returns:
        Dict with synced_count, skipped_count, error_count.
    """
    log = logger.bind(user_id=user_id, task="sync_strava_activities")
    log.info("strava_sync_started")

    session = self.session_maker()
    svc = StravaService()
    try:
        integration = _get_strava_integration(session, user_id)
        access_token = _get_valid_access_token(session, integration)

        # Determine sync window
        if integration.last_sync_at is not None:
            since_epoch = int(integration.last_sync_at.timestamp())
        else:
            since_epoch = int(
                (datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)).timestamp()
            )

        # Fetch activities page by page
        synced = 0
        skipped = 0
        errors = 0
        page = 1

        while True:
            if not _rate_limiter.can_make_request():
                _rate_limiter.wait_if_needed()

            activities = svc.fetch_activities_since(access_token, since_epoch, page)
            _rate_limiter.record_request()

            if not activities:
                break

            for act in activities:
                result = _import_strava_activity(session, svc, access_token, act, user_id)
                if result == "synced":
                    synced += 1
                elif result == "skipped":
                    skipped += 1
                else:
                    errors += 1

            if len(activities) < 100:
                break
            page += 1

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

        result_dict = {
            "synced_count": synced,
            "skipped_count": skipped,
            "error_count": errors,
        }
        log.info("strava_sync_complete", **result_dict)
        return result_dict

    except (StravaAuthError, StravaSyncError) as exc:
        session.rollback()
        log.exception("strava_sync_failed", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    except Exception as exc:
        session.rollback()
        log.exception("strava_sync_unexpected_error", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    finally:
        svc.close()
        session.close()


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.strava_sync.fetch_strava_activity",
    queue="high_priority",
)
def fetch_strava_activity(
    self: BaseTask, user_id: int, strava_activity_id: int
) -> dict[str, Any]:
    """Fetch and import a single Strava activity by ID.

    Args:
        user_id: User ID.
        strava_activity_id: Strava activity ID to fetch.

    Returns:
        Dict with status and activity_id.
    """
    log = logger.bind(user_id=user_id, strava_activity_id=strava_activity_id)
    log.info("strava_single_fetch_started")

    session = self.session_maker()
    svc = StravaService()
    try:
        integration = _get_strava_integration(session, user_id)
        access_token = _get_valid_access_token(session, integration)

        strava_activity = {"id": strava_activity_id}
        result = _import_strava_activity(session, svc, access_token, strava_activity, user_id)
        session.commit()

        log.info("strava_single_fetch_complete", result=result)
        return {"status": result, "strava_activity_id": strava_activity_id}

    except (StravaAuthError, StravaSyncError) as exc:
        session.rollback()
        log.exception("strava_single_fetch_failed", error=str(exc))
        raise

    except Exception as exc:
        session.rollback()
        log.exception("strava_single_fetch_unexpected_error", error=str(exc))
        raise

    finally:
        svc.close()
        session.close()


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.strava_sync.process_strava_webhook",
    queue="high_priority",
)
def process_strava_webhook(self: BaseTask, event_data: dict[str, Any]) -> dict[str, Any]:
    """Process a Strava webhook event.

    Handles create, update, and delete aspect types for activities.

    Args:
        event_data: Webhook event payload from Strava.

    Returns:
        Dict with action taken and relevant IDs.
    """
    log = logger.bind(event_data=event_data)
    log.info("strava_webhook_processing")

    aspect_type = event_data.get("aspect_type")
    object_id = event_data.get("object_id")
    owner_id = event_data.get("owner_id")

    # For Phase 1, map owner_id to our single user
    user_id = 1  # DEFAULT_USER_ID

    session = self.session_maker()
    try:
        if aspect_type == "create":
            # Import the new activity
            integration = _get_strava_integration(session, user_id)
            access_token = _get_valid_access_token(session, integration)

            svc = StravaService()
            try:
                strava_activity = {"id": object_id}
                result = _import_strava_activity(
                    session, svc, access_token, strava_activity, user_id
                )
                session.commit()
            finally:
                svc.close()

            return {"action": "created", "strava_id": object_id, "result": result}

        elif aspect_type == "update":
            # Re-fetch and update the activity
            existing_stmt = select(Activity).where(
                Activity.external_id == str(object_id),
                Activity.source == ActivitySource.strava,
            )
            existing = session.execute(existing_stmt).scalar_one_or_none()

            if existing is not None:
                integration = _get_strava_integration(session, user_id)
                access_token = _get_valid_access_token(session, integration)

                svc = StravaService()
                try:
                    detail = svc.fetch_activity_detail(access_token, int(object_id))
                    activity_data, _ = StravaService.convert_strava_to_internal(detail, {})

                    existing.name = activity_data["name"]
                    existing.sport_type = activity_data.get("sport_type")
                    session.commit()
                finally:
                    svc.close()

            return {"action": "updated", "strava_id": object_id}

        elif aspect_type == "delete":
            # Delete the activity if it exists
            existing_stmt = select(Activity).where(
                Activity.external_id == str(object_id),
                Activity.source == ActivitySource.strava,
            )
            existing = session.execute(existing_stmt).scalar_one_or_none()

            if existing is not None:
                session.delete(existing)
                session.commit()
                log.info("strava_activity_deleted", strava_id=object_id)

            return {"action": "deleted", "strava_id": object_id}

        else:
            log.debug("strava_webhook_unknown_aspect", aspect_type=aspect_type)
            return {"action": "ignored", "reason": f"unknown aspect_type: {aspect_type}"}

    except Exception as exc:
        session.rollback()
        log.exception("strava_webhook_processing_error", error=str(exc))
        raise

    finally:
        session.close()


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.strava_sync.strava_historical_backfill",
    queue="low_priority",
)
def strava_historical_backfill(self: BaseTask, user_id: int) -> dict[str, Any]:
    """Backfill all historical Strava activities for a user.

    Fetches every activity from the user's Strava account and imports
    any that are not already in the database.

    Args:
        user_id: User ID to backfill for.

    Returns:
        Dict with synced_count, skipped_count, error_count.
    """
    log = logger.bind(user_id=user_id, task="strava_historical_backfill")
    log.info("strava_backfill_started")

    session = self.session_maker()
    svc = StravaService()
    try:
        integration = _get_strava_integration(session, user_id)
        access_token = _get_valid_access_token(session, integration)

        all_activities = svc.backfill_all_activities(access_token)
        log.info("strava_backfill_activities_fetched", total=len(all_activities))

        synced = 0
        skipped = 0
        errors = 0

        for act in all_activities:
            if not _rate_limiter.can_make_request():
                _rate_limiter.wait_if_needed()

            result = _import_strava_activity(session, svc, access_token, act, user_id)
            if result == "synced":
                synced += 1
            elif result == "skipped":
                skipped += 1
            else:
                errors += 1

            # Commit in batches of 10
            if (synced + skipped + errors) % 10 == 0:
                session.commit()

        # Final commit and update
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

        result_dict = {
            "synced_count": synced,
            "skipped_count": skipped,
            "error_count": errors,
        }
        log.info("strava_backfill_complete", **result_dict)
        return result_dict

    except (StravaAuthError, StravaSyncError) as exc:
        session.rollback()
        log.exception("strava_backfill_failed", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    except Exception as exc:
        session.rollback()
        log.exception("strava_backfill_unexpected_error", error=str(exc))
        _update_integration_error(session, user_id, str(exc))
        raise

    finally:
        svc.close()
        session.close()
