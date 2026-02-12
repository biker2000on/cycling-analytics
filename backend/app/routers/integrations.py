"""Integration API endpoints — Garmin Connect, Strava, etc."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.schemas.integration import GarminConnectRequest, IntegrationStatusResponse
from app.services.garmin_service import (
    GarminAuthError,
    GarminService,
    GarminSyncError,
    encrypt_credentials,
)
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

DEFAULT_USER_ID = 1  # Phase 1: no auth, single seed user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_garmin_integration(
    db: AsyncSession,
    user_id: int = DEFAULT_USER_ID,
) -> Integration | None:
    """Fetch the Garmin integration for a user, or None."""
    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == IntegrationProvider.garmin,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/garmin/connect",
    response_model=IntegrationStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect Garmin account",
)
async def connect_garmin(
    body: GarminConnectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationStatusResponse:
    """Save encrypted Garmin credentials and verify login.

    If an existing integration exists, it will be updated with new credentials.
    """
    settings = get_settings()

    # Test login before saving credentials
    svc = GarminService(body.email, body.password)
    try:
        svc.login()
    except GarminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Garmin authentication failed: {exc}",
        )
    except GarminSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not connect to Garmin: {exc}",
        )

    # Encrypt credentials
    encrypted = encrypt_credentials(body.email, body.password, settings.SECRET_KEY)

    # Check for existing integration
    integration = await _get_garmin_integration(db)

    if integration is not None:
        # Update existing
        integration.credentials_encrypted = encrypted
        integration.status = IntegrationStatus.active
        integration.sync_enabled = True
        integration.error_message = None
        logger.info("garmin_integration_updated", integration_id=integration.id)
    else:
        # Create new
        integration = Integration(
            user_id=DEFAULT_USER_ID,
            provider=IntegrationProvider.garmin,
            credentials_encrypted=encrypted,
            sync_enabled=True,
            status=IntegrationStatus.active,
        )
        db.add(integration)
        logger.info("garmin_integration_created")

    await db.flush()

    return IntegrationStatusResponse.model_validate(integration)


@router.post(
    "/garmin/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual Garmin sync",
)
async def trigger_garmin_sync(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Queue a manual Garmin sync for activities and health data."""
    integration = await _get_garmin_integration(db)

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Garmin integration found. Connect your account first.",
        )

    if integration.status == IntegrationStatus.disconnected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garmin integration is disconnected. Reconnect your account.",
        )

    # Queue Celery tasks on low_priority queue
    activity_task = celery_app.send_task(
        "app.workers.tasks.garmin_sync.sync_garmin_activities",
        args=[DEFAULT_USER_ID],
        queue="low_priority",
    )
    health_task = celery_app.send_task(
        "app.workers.tasks.garmin_sync.sync_garmin_health",
        args=[DEFAULT_USER_ID],
        queue="low_priority",
    )

    logger.info(
        "garmin_sync_triggered",
        activity_task_id=activity_task.id,
        health_task_id=health_task.id,
    )

    return {
        "activity_task_id": activity_task.id,
        "health_task_id": health_task.id,
        "message": "Garmin sync queued successfully",
    }


@router.get(
    "/garmin/status",
    response_model=IntegrationStatusResponse,
    summary="Get Garmin integration status",
)
async def get_garmin_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationStatusResponse:
    """Return current Garmin integration status."""
    integration = await _get_garmin_integration(db)

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Garmin integration found.",
        )

    return IntegrationStatusResponse.model_validate(integration)


@router.delete(
    "/garmin/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Garmin account",
)
async def disconnect_garmin(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Clear Garmin credentials and disable sync."""
    integration = await _get_garmin_integration(db)

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Garmin integration found.",
        )

    integration.credentials_encrypted = None
    integration.sync_enabled = False
    integration.status = IntegrationStatus.disconnected
    integration.error_message = None

    logger.info("garmin_integration_disconnected", integration_id=integration.id)
