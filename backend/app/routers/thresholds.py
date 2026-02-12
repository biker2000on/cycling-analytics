"""Threshold management endpoints -- CRUD for FTP threshold history."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_or_default, get_db
from app.models.threshold import Threshold
from app.models.user import User
from app.schemas.threshold import ThresholdCreate, ThresholdHistory, ThresholdResponse
from app.services.threshold_service import estimate_threshold_8min, estimate_threshold_20min

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/thresholds", tags=["thresholds"])


@router.get(
    "",
    response_model=ThresholdHistory,
    summary="Get threshold history",
)
async def get_thresholds(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    method: str | None = Query(default=None, description="Filter by threshold method"),
) -> ThresholdHistory:
    """Return full threshold history for the user, optionally filtered by method."""
    stmt = (
        select(Threshold)
        .where(Threshold.user_id == current_user.id)
        .order_by(Threshold.effective_date.desc(), Threshold.created_at.desc())
    )
    if method is not None:
        stmt = stmt.where(Threshold.method == method)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return ThresholdHistory(
        thresholds=[ThresholdResponse.model_validate(row) for row in rows]
    )


@router.post(
    "",
    response_model=ThresholdResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new threshold entry",
)
async def create_threshold(
    data: ThresholdCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> ThresholdResponse:
    """Create a new threshold entry (typically manual set)."""
    # Check for existing threshold with same user/method/date
    existing_stmt = select(Threshold).where(
        Threshold.user_id == current_user.id,
        Threshold.method == data.method,
        Threshold.effective_date == data.effective_date,
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Threshold already exists for method '{data.method}' "
                f"on {data.effective_date}. Use PUT to update."
            ),
        )

    now = datetime.now(UTC)
    threshold = Threshold(
        user_id=current_user.id,
        method=data.method,
        effective_date=data.effective_date,
        ftp_watts=data.ftp_watts,
        is_active=True,
        notes=data.notes,
    )
    db.add(threshold)
    await db.flush()

    logger.info(
        "threshold_created",
        user_id=current_user.id,
        method=data.method,
        ftp_watts=str(data.ftp_watts),
        effective_date=str(data.effective_date),
    )

    return ThresholdResponse(
        id=threshold.id if threshold.id is not None else 0,
        method=threshold.method,
        ftp_watts=threshold.ftp_watts,
        effective_date=threshold.effective_date,
        source_activity_id=threshold.source_activity_id,
        is_active=threshold.is_active,
        notes=threshold.notes,
        created_at=threshold.created_at if threshold.created_at is not None else now,
    )


@router.get(
    "/current",
    response_model=ThresholdResponse,
    summary="Get current active threshold",
)
async def get_current_threshold(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    method: str = Query(default="manual", description="Threshold method"),
) -> ThresholdResponse:
    """Return the most recent active threshold for the specified method."""
    stmt = (
        select(Threshold)
        .where(
            Threshold.user_id == current_user.id,
            Threshold.method == method,
            Threshold.is_active.is_(True),
        )
        .order_by(Threshold.effective_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    threshold = result.scalar_one_or_none()

    if threshold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active threshold found for method '{method}'.",
        )

    return ThresholdResponse.model_validate(threshold)


@router.put(
    "/{threshold_id}/activate",
    response_model=ThresholdResponse,
    summary="Activate a threshold entry",
)
async def activate_threshold(
    threshold_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> ThresholdResponse:
    """Set a specific threshold entry as active."""
    stmt = select(Threshold).where(
        Threshold.id == threshold_id,
        Threshold.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    threshold = result.scalar_one_or_none()

    if threshold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Threshold {threshold_id} not found.",
        )

    threshold.is_active = True
    await db.flush()

    logger.info(
        "threshold_activated",
        threshold_id=threshold_id,
        method=threshold.method,
        ftp_watts=str(threshold.ftp_watts),
    )

    return ThresholdResponse.model_validate(threshold)


@router.post(
    "/estimate/{method}",
    response_model=ThresholdResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run auto-detection for a threshold method",
)
async def estimate_threshold(
    method: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> ThresholdResponse:
    """Run auto-detection for the specified threshold method.

    Supported methods:
    - pct_20min: 95% of best 20-minute power
    - pct_8min: 90% of best 8-minute power
    """
    if method == "pct_20min":
        threshold = await estimate_threshold_20min(current_user.id, db)
    elif method == "pct_8min":
        threshold = await estimate_threshold_8min(current_user.id, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported estimation method: '{method}'. "
            "Supported: pct_20min, pct_8min.",
        )

    if threshold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No qualifying rides found for method '{method}'.",
        )

    await db.flush()
    return ThresholdResponse.model_validate(threshold)
