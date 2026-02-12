"""User settings endpoints — FTP management."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user_settings import UserSettings
from app.schemas.settings import FtpResponse, FtpSetting

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_USER_ID = 1  # Phase 1: no auth, single seed user


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
