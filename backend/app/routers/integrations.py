"""Integration API endpoints — Garmin Connect, Strava, etc."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.schemas.integration import (
    GarminConnectRequest,
    IntegrationStatusResponse,
    StravaAuthUrl,
    StravaCallbackResponse,
    StravaStatus,
)
from app.services.garmin_service import (
    GarminAuthError,
    GarminService,
    GarminSyncError,
    encrypt_credentials,
)
from app.services.strava_service import (
    StravaAuthError,
    StravaService,
    encrypt_token,
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


# ---------------------------------------------------------------------------
# Strava helpers
# ---------------------------------------------------------------------------


async def _get_strava_integration(
    db: AsyncSession,
    user_id: int = DEFAULT_USER_ID,
) -> Integration | None:
    """Fetch the Strava integration for a user, or None."""
    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == IntegrationProvider.strava,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Strava endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/strava/authorize",
    response_model=StravaAuthUrl,
    summary="Get Strava OAuth2 authorization URL",
)
async def strava_authorize() -> StravaAuthUrl:
    """Return the Strava OAuth2 authorization URL for the user to visit."""
    settings = get_settings()
    svc = StravaService()
    try:
        url = svc.build_auth_url(settings.STRAVA_REDIRECT_URI)
    finally:
        svc.close()
    return StravaAuthUrl(url=url)


@router.get(
    "/strava/callback",
    response_model=StravaCallbackResponse,
    summary="Strava OAuth2 callback",
)
async def strava_callback(
    code: Annotated[str, Query(description="Authorization code from Strava")],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StravaCallbackResponse:
    """Exchange Strava authorization code for tokens and store them."""
    settings = get_settings()

    svc = StravaService()
    try:
        token_data = svc.exchange_code(code, settings.STRAVA_REDIRECT_URI)
    except StravaAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Strava authentication failed: {exc}",
        )
    finally:
        svc.close()

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=UTC)
    athlete = token_data.get("athlete", {})
    athlete_id = str(athlete.get("id", ""))

    # Encrypt tokens
    access_encrypted = encrypt_token(access_token, settings.SECRET_KEY)
    refresh_encrypted = encrypt_token(refresh_token, settings.SECRET_KEY)

    # Upsert integration
    integration = await _get_strava_integration(db)

    if integration is not None:
        integration.access_token_encrypted = access_encrypted
        integration.refresh_token_encrypted = refresh_encrypted
        integration.token_expires_at = expires_at
        integration.athlete_id = athlete_id
        integration.status = IntegrationStatus.active
        integration.sync_enabled = True
        integration.error_message = None
        logger.info("strava_integration_updated", integration_id=integration.id)
    else:
        integration = Integration(
            user_id=DEFAULT_USER_ID,
            provider=IntegrationProvider.strava,
            access_token_encrypted=access_encrypted,
            refresh_token_encrypted=refresh_encrypted,
            token_expires_at=expires_at,
            athlete_id=athlete_id,
            sync_enabled=True,
            status=IntegrationStatus.active,
        )
        db.add(integration)
        logger.info("strava_integration_created", athlete_id=athlete_id)

    await db.flush()

    return StravaCallbackResponse(connected=True, athlete_id=athlete_id)


@router.get(
    "/strava/status",
    response_model=StravaStatus,
    summary="Get Strava integration status",
)
async def strava_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StravaStatus:
    """Return current Strava integration connection status."""
    integration = await _get_strava_integration(db)

    if integration is None:
        return StravaStatus(connected=False)

    return StravaStatus(
        connected=integration.status == IntegrationStatus.active,
        athlete_id=integration.athlete_id,
        last_sync=integration.last_sync_at,
    )


@router.delete(
    "/strava/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Strava account",
)
async def strava_disconnect(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Clear Strava tokens and disable sync."""
    integration = await _get_strava_integration(db)

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Strava integration found.",
        )

    integration.access_token_encrypted = None
    integration.refresh_token_encrypted = None
    integration.token_expires_at = None
    integration.athlete_id = None
    integration.credentials_encrypted = None
    integration.sync_enabled = False
    integration.status = IntegrationStatus.disconnected
    integration.error_message = None

    logger.info("strava_integration_disconnected", integration_id=integration.id)


@router.post(
    "/strava/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual Strava sync",
)
async def trigger_strava_sync(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Queue a manual Strava activity sync."""
    integration = await _get_strava_integration(db)

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Strava integration found. Connect your account first.",
        )

    if integration.status == IntegrationStatus.disconnected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strava integration is disconnected. Reconnect your account.",
        )

    task = celery_app.send_task(
        "app.workers.tasks.strava_sync.sync_strava_activities",
        args=[DEFAULT_USER_ID],
        queue="low_priority",
    )

    logger.info("strava_sync_triggered", task_id=task.id)

    return {
        "task_id": task.id,
        "message": "Strava sync queued successfully",
    }


@router.post(
    "/strava/backfill",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Strava historical backfill",
)
async def trigger_strava_backfill(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Queue a full historical backfill of all Strava activities."""
    integration = await _get_strava_integration(db)

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Strava integration found. Connect your account first.",
        )

    if integration.status == IntegrationStatus.disconnected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strava integration is disconnected. Reconnect your account.",
        )

    task = celery_app.send_task(
        "app.workers.tasks.strava_sync.strava_historical_backfill",
        args=[DEFAULT_USER_ID],
        queue="low_priority",
    )

    logger.info("strava_backfill_triggered", task_id=task.id)

    return {
        "task_id": task.id,
        "message": "Strava historical backfill queued successfully",
    }
