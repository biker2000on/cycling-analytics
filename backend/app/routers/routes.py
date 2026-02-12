"""Activity route endpoint — GeoJSON LineString from GPS stream data."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_or_default, get_db
from app.models.activity import Activity
from app.models.user import User
from app.schemas.route import RouteGeoJSON
from app.services.stream_service import get_activity_route

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/activities", tags=["routes"])


@router.get(
    "/{activity_id}/route",
    response_model=RouteGeoJSON,
    summary="Get GeoJSON route for an activity",
)
async def get_route(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> RouteGeoJSON:
    """Return a GeoJSON Feature with a LineString geometry for the GPS track.

    Returns 404 if the activity does not exist or has no GPS data.
    """
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )

    route = await get_activity_route(
        activity_id,
        db,
        activity_name=activity.name,
        sport_type=activity.sport_type,
    )

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No GPS data for activity {activity_id}.",
        )

    return route
