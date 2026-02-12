"""User settings endpoints — FTP management and user preferences."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_or_default, get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    FtpResponse,
    FtpSetting,
    UserSettingsResponse,
    UserSettingsUpdate,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Valid threshold methods
VALID_THRESHOLD_METHODS = {"manual", "pct_20min", "pct_8min", "xert_model"}

# Valid unit systems
VALID_UNIT_SYSTEMS = {"metric", "imperial"}


@router.get(
    "",
    response_model=UserSettingsResponse,
    summary="Get full user preferences",
)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> UserSettingsResponse:
    """Return the full user preferences for the current user."""
    stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
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
            unit_system="metric",
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
    current_user: Annotated[User, Depends(get_current_user_or_default)],
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

    # Validate unit system if provided
    if data.unit_system is not None and data.unit_system not in VALID_UNIT_SYSTEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid unit system: '{data.unit_system}'. "
                f"Valid: {', '.join(sorted(VALID_UNIT_SYSTEMS))}"
            ),
        )

    stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = UserSettings(
            user_id=current_user.id,
            ftp_method="manual",
            preferred_threshold_method="manual",
            calendar_start_day=1,
            unit_system="metric",
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
    if data.unit_system is not None:
        settings.unit_system = data.unit_system

    await db.flush()

    logger.info(
        "settings_updated",
        user_id=current_user.id,
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
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> FtpResponse:
    """Create or update the FTP setting for the current user."""
    stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if settings is None:
        settings = UserSettings(
            user_id=current_user.id,
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

    logger.info("ftp_updated", user_id=current_user.id, ftp_watts=str(data.ftp_watts))

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
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> FtpResponse:
    """Retrieve the current FTP setting for the current user."""
    stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
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
