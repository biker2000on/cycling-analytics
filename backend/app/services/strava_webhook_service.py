"""Strava webhook event validation and routing.

Handles incoming webhook events from Strava and routes them
to appropriate Celery tasks.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Strava webhook object types
OBJECT_TYPE_ACTIVITY = "activity"
OBJECT_TYPE_ATHLETE = "athlete"

# Strava webhook aspect types
ASPECT_CREATE = "create"
ASPECT_UPDATE = "update"
ASPECT_DELETE = "delete"

# Default user ID (Phase 1: single seed user)
DEFAULT_USER_ID = 1


def validate_webhook(event_data: dict[str, Any]) -> bool:
    """Validate that a webhook event has the required fields.

    Args:
        event_data: Parsed JSON body from Strava webhook POST.

    Returns:
        True if the event has required fields.
    """
    required_fields = {"object_type", "aspect_type", "object_id", "owner_id"}
    return required_fields.issubset(event_data.keys())


def route_webhook_event(event_data: dict[str, Any]) -> str | None:
    """Route a validated Strava webhook event to the appropriate Celery task.

    Args:
        event_data: Validated webhook event dict.

    Returns:
        Celery task ID if a task was queued, None if event was ignored.
    """
    object_type = event_data.get("object_type")
    aspect_type = event_data.get("aspect_type")
    object_id = event_data.get("object_id")
    owner_id = event_data.get("owner_id")

    logger.info(
        "strava_webhook_received",
        object_type=object_type,
        aspect_type=aspect_type,
        object_id=object_id,
        owner_id=owner_id,
    )

    if object_type != OBJECT_TYPE_ACTIVITY:
        logger.debug("strava_webhook_ignored_non_activity", object_type=object_type)
        return None

    # Queue the webhook processing task
    task = celery_app.send_task(
        "app.workers.tasks.strava_sync.process_strava_webhook",
        args=[event_data],
        queue="high_priority",
    )

    logger.info(
        "strava_webhook_task_queued",
        task_id=task.id,
        aspect_type=aspect_type,
        object_id=object_id,
    )

    return task.id
