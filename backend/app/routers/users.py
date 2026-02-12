"""User profile endpoints (Phase 5)."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user_or_default
from app.models.user import User
from app.schemas.user import UserProfile, UserProfileUpdate

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current user profile",
)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> UserProfile:
    """Return the current user's full profile."""
    return UserProfile.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserProfile,
    summary="Update current user profile",
)
async def update_profile(
    data: UserProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> UserProfile:
    """Update the current user's profile fields."""
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.weight_kg is not None:
        current_user.weight_kg = data.weight_kg
    if data.date_of_birth is not None:
        current_user.date_of_birth = data.date_of_birth
    if data.timezone is not None:
        current_user.timezone = data.timezone

    logger.info("user_profile_updated", user_id=current_user.id)

    return UserProfile.model_validate(current_user)
