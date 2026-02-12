"""Setup wizard endpoints — initial user creation (Phase 5)."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.auth import TokenResponse
from app.schemas.setup import InitialSetupRequest, SetupStatus
from app.security import create_access_token, create_refresh_token, hash_password

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])

ACCESS_TOKEN_EXPIRES_SECONDS = 1800


@router.get(
    "/status",
    response_model=SetupStatus,
    summary="Check setup status",
)
async def get_setup_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SetupStatus:
    """Return whether initial setup has been completed (any users exist)."""
    stmt = select(func.count()).select_from(User)
    result = await db.execute(stmt)
    user_count = result.scalar_one()

    return SetupStatus(
        setup_complete=user_count > 0,
        user_count=user_count,
    )


@router.post(
    "/init",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create initial user (first-time setup)",
)
async def initial_setup(
    data: InitialSetupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Create the first user account. Only works when no users exist.

    This endpoint does not require authentication.
    """
    # Check if any users exist
    stmt = select(func.count()).select_from(User)
    result = await db.execute(stmt)
    user_count = result.scalar_one()

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup already completed. Use /auth/register to create additional users.",
        )

    # Create the first user
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    await db.flush()

    # Create user settings with optional FTP
    if data.ftp_watts is not None:
        settings = UserSettings(
            user_id=user.id,
            ftp_watts=data.ftp_watts,
            ftp_method="manual",
            ftp_updated_at=datetime.now(UTC),
        )
        db.add(settings)
        await db.flush()

    logger.info("initial_setup_completed", user_id=user.id, email=data.email)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRES_SECONDS,
    )
