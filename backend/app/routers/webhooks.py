"""Webhook endpoints — Strava push notifications."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import get_settings
from app.services.strava_webhook_service import route_webhook_event, validate_webhook

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get(
    "/strava",
    summary="Strava webhook verification (hub.challenge)",
)
async def strava_webhook_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> dict[str, str]:
    """Handle Strava webhook subscription verification.

    Strava sends a GET request with hub.mode, hub.challenge, and
    hub.verify_token. We must verify the token and echo back the challenge.
    """
    settings = get_settings()

    if hub_mode != "subscribe":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid hub.mode",
        )

    if hub_verify_token != settings.STRAVA_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid verify token",
        )

    logger.info("strava_webhook_verified", challenge=hub_challenge)
    return {"hub.challenge": hub_challenge}


@router.post(
    "/strava",
    status_code=status.HTTP_200_OK,
    summary="Strava webhook event receiver",
)
async def strava_webhook_receive(request: Request) -> dict[str, Any]:
    """Receive and process Strava webhook events.

    Strava expects a 200 response within 2 seconds, so we queue
    a Celery task and return immediately.
    """
    try:
        event_data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    if not validate_webhook(event_data):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required webhook fields",
        )

    task_id = route_webhook_event(event_data)

    return {
        "status": "received",
        "task_id": task_id,
    }
