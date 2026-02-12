"""User settings endpoints — FTP management and user preferences."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    FtpResponse,
    FtpSetting,
    UserSettingsResponse,
    UserSettingsUpdate,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_USER_ID = 1  # Phase 1: no auth, single seed user

# Valid threshold methods
VALID_THRESHOLD_METHODS = {"manual", "pct_20min", "pct_8min", "xert_model"}


@router.get(
    "",
    response_model=UserSettingsResponse,
    summary="Get full user preferences",
)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """Return the full user preferences for the seed user."""
    stmt = select(UserSettings).where(UserSettings.user_id == DEFAULT_USER_ID)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings is None:
        # Return defaults when no settings record exists
        return UserSettingsResponse(
            ftp_watts=None,
            ftp_method="manual",
            preferred_threshold_method="manual",
            calendar_start_day=1,
            weight_kg=None,
            date_of_birth=None,
        )

    return UserSettingsResponse.model_validate(settings)


@router.put(
    "",
    response_model=UserSettingsResponse,
    summary="Update user preferences",
)
async def update_settings(
    data: UserSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """Update user preferences (threshold method, calendar, weight, DOB)."""
    # Validate threshold method if provided
    if (
        data.preferred_threshold_method is not None
        and data.preferred_threshold_method not in VALID_THRESHOLD_METHODS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid threshold method: '{data.preferred_threshold_method}'. "
                f"Valid methods: {', '.join(sorted(VALID_THRESHOLD_METHODS))}"
            ),
        )

    stmt = select(UserSettings).where(UserSettings.user_id == DEFAULT_USER_ID)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = UserSettings(
            user_id=DEFAULT_USER_ID,
            ftp_method="manual",
            preferred_threshold_method="manual",
            calendar_start_day=1,
        )
        db.add(settings)

    # Apply only provided fields
    if data.preferred_threshold_method is not None:
        settings.preferred_threshold_method = data.preferred_threshold_method
    if data.calendar_start_day is not None:
        settings.calendar_start_day = data.calendar_start_day
    if data.weight_kg is not None:
        settings.weight_kg = data.weight_kg
    if data.date_of_birth is not None:
        settings.date_of_birth = data.date_of_birth

    await db.flush()

    logger.info(
        "settings_updated",
        user_id=DEFAULT_USER_ID,
        preferred_method=settings.preferred_threshold_method,
    )

    return UserSettingsResponse.model_validate(settings)


@router.post(
    "/ftp",
    response_model=FtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Set or update FTP",
)
async def set_ftp(
    data: FtpSetting,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FtpResponse:
    """Create or update the FTP setting for the seed user."""
    stmt = select(UserSettings).where(UserSettings.user_id == DEFAULT_USER_ID)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if settings is None:
        settings = UserSettings(
            user_id=DEFAULT_USER_ID,
            ftp_watts=data.ftp_watts,
            ftp_method="manual",
            ftp_updated_at=now,
        )
        db.add(settings)
    else:
        settings.ftp_watts = data.ftp_watts
        settings.ftp_method = "manual"
        settings.ftp_updated_at = now

    await db.flush()

    logger.info("ftp_updated", user_id=DEFAULT_USER_ID, ftp_watts=str(data.ftp_watts))

    return FtpResponse(
        ftp_watts=settings.ftp_watts,
        ftp_method=settings.ftp_method,
        updated_at=settings.ftp_updated_at,
    )


@router.get(
    "/ftp",
    response_model=FtpResponse,
    summary="Get current FTP",
)
async def get_ftp(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FtpResponse:
    """Retrieve the current FTP setting for the seed user."""
    stmt = select(UserSettings).where(UserSettings.user_id == DEFAULT_USER_ID)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings is None or settings.ftp_watts is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FTP not configured. Use POST /settings/ftp to set it.",
        )

    return FtpResponse(
        ftp_watts=settings.ftp_watts,
        ftp_method=settings.ftp_method,
        updated_at=settings.ftp_updated_at,
    )
