"""Metrics endpoints — fitness (CTL/ATL/TSB), activity metrics."""

from datetime import date, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.activity_metrics import ActivityMetrics
from app.models.fitness_metrics import DailyFitness
from app.schemas.metrics import (
    ActivityMetricsResponse,
    FitnessDataPoint,
    FitnessTimeSeries,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])

DEFAULT_USER_ID = 1  # Phase 1: no auth, single seed user


@router.get(
    "/fitness",
    response_model=FitnessTimeSeries,
    summary="Get fitness time series (CTL/ATL/TSB)",
)
async def get_fitness(
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = Query(default=None, description="Start date (default: 90 days ago)"),
    end_date: date | None = Query(default=None, description="End date (default: today)"),
    threshold_method: str = Query(default="manual", description="Threshold method"),
) -> FitnessTimeSeries:
    """Return daily CTL, ATL, TSB values for the given date range.

    Defaults to the last 90 days if no date range specified.
    """
    today = date.today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=90)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    stmt = (
        select(DailyFitness)
        .where(
            DailyFitness.user_id == DEFAULT_USER_ID,
            DailyFitness.threshold_method == threshold_method,
            DailyFitness.date >= start_date,
            DailyFitness.date <= end_date,
        )
        .order_by(DailyFitness.date)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    data = [
        FitnessDataPoint(
            date=row.date,
            tss_total=row.tss_total,
            ctl=row.ctl,
            atl=row.atl,
            tsb=row.tsb,
        )
        for row in rows
    ]

    return FitnessTimeSeries(
        data=data,
        start_date=start_date,
        end_date=end_date,
        threshold_method=threshold_method,
    )


@router.get(
    "/activity/{activity_id}",
    response_model=ActivityMetricsResponse,
    summary="Get computed metrics for an activity",
)
async def get_activity_metrics(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    threshold_method: str = Query(default="manual", description="Threshold method"),
) -> ActivityMetricsResponse:
    """Return computed Coggan metrics for a single activity."""
    stmt = select(ActivityMetrics).where(
        ActivityMetrics.activity_id == activity_id,
        ActivityMetrics.user_id == DEFAULT_USER_ID,
        ActivityMetrics.threshold_method == threshold_method,
    )
    result = await db.execute(stmt)
    metrics = result.scalar_one_or_none()

    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metrics found for activity {activity_id}.",
        )

    return ActivityMetricsResponse.model_validate(metrics)
