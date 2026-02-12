"""Activity stream endpoints — full data and downsampled summaries."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.activity import Activity
from app.schemas.stream import StreamResponse, StreamSummaryResponse
from app.services.stream_service import get_activity_streams, get_activity_streams_summary

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/activities", tags=["streams"])

DEFAULT_USER_ID = 1  # Phase 1: no auth, single seed user


async def _get_validated_activity(
    activity_id: int,
    db: AsyncSession,
) -> Activity:
    """Fetch activity and raise 404 if not found or not owned by default user."""
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == DEFAULT_USER_ID,
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )
    return activity


@router.get(
    "/{activity_id}/streams",
    response_model=StreamResponse,
    summary="Get full stream data for an activity",
)
async def get_streams(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamResponse:
    """Return all per-second stream data in columnar format."""
    await _get_validated_activity(activity_id, db)
    return await get_activity_streams(activity_id, db)


@router.get(
    "/{activity_id}/streams/summary",
    response_model=StreamSummaryResponse,
    summary="Get downsampled stream data for charts",
)
async def get_streams_summary(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    points: int = Query(default=500, ge=2, le=5000, description="Target point count"),
) -> StreamSummaryResponse:
    """Return LTTB-downsampled stream data for efficient chart rendering."""
    await _get_validated_activity(activity_id, db)
    return await get_activity_streams_summary(activity_id, points, db)
