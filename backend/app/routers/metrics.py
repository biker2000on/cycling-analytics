"""Metrics endpoints — fitness (CTL/ATL/TSB), activity metrics, period summary,
power analysis, and HR analysis."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_current_user_or_default, get_db
from app.models.activity import Activity
from app.models.activity_metrics import ActivityMetrics
from app.models.fitness_metrics import DailyFitness
from app.models.user import User
from app.schemas.metrics import (
    ActivityMetricsResponse,
    FitnessDataPoint,
    FitnessTimeSeries,
    HRAnalysisResponse,
    PeriodSummary,
    PowerAnalysisResponse,
)
from app.services.cache_service import (
    CacheService,
    fitness_cache_key,
    metrics_cache_key,
    summary_cache_key,
)
from app.services.power_analysis_service import get_hr_analysis, get_power_analysis

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Cache TTL constants (seconds)
FITNESS_CACHE_TTL = 300  # 5 minutes
METRICS_CACHE_TTL = 600  # 10 minutes (activity metrics rarely change)
SUMMARY_CACHE_TTL = 300  # 5 minutes


def _get_cache() -> CacheService:
    """Create a CacheService instance from application settings."""
    settings = get_settings()
    return CacheService(redis_url=settings.REDIS_URL, db=settings.REDIS_CACHE_DB)


@router.get(
    "/fitness",
    response_model=FitnessTimeSeries,
    summary="Get fitness time series (CTL/ATL/TSB)",
)
async def get_fitness(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    start_date: date | None = Query(default=None, description="Start date (default: 90 days ago)"),
    end_date: date | None = Query(default=None, description="End date (default: today)"),
    threshold_method: str = Query(default="manual", description="Threshold method"),
) -> FitnessTimeSeries:
    """Return daily CTL, ATL, TSB values for the given date range.

    Defaults to the last 90 days if no date range specified.
    Results are cached in Redis for 5 minutes.
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

    # Check cache
    cache = _get_cache()
    cache_key = fitness_cache_key(
        current_user.id, threshold_method, str(start_date), str(end_date)
    )
    try:
        cached = await cache.get_json(cache_key)
        if cached is not None:
            logger.debug("cache_hit", key=cache_key)
            return FitnessTimeSeries.model_validate(cached)
    finally:
        await cache.close()

    # Cache miss — query DB
    stmt = (
        select(DailyFitness)
        .where(
            DailyFitness.user_id == current_user.id,
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

    response = FitnessTimeSeries(
        data=data,
        start_date=start_date,
        end_date=end_date,
        threshold_method=threshold_method,
    )

    # Write to cache (fire-and-forget, errors are swallowed by CacheService)
    cache = _get_cache()
    try:
        await cache.set_json(cache_key, response.model_dump(mode="json"), FITNESS_CACHE_TTL)
    finally:
        await cache.close()

    return response


@router.get(
    "/activities/{activity_id}",
    response_model=ActivityMetricsResponse,
    summary="Get computed metrics for an activity",
)
async def get_activity_metrics(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    threshold_method: str = Query(default="manual", description="Threshold method"),
) -> ActivityMetricsResponse:
    """Return computed Coggan metrics for a single activity.

    Results are cached in Redis for 10 minutes.
    """
    # Check cache
    cache = _get_cache()
    cache_key = metrics_cache_key(activity_id, threshold_method)
    try:
        cached = await cache.get_json(cache_key)
        if cached is not None:
            logger.debug("cache_hit", key=cache_key)
            return ActivityMetricsResponse.model_validate(cached)
    finally:
        await cache.close()

    # Cache miss — query DB
    stmt = select(ActivityMetrics).where(
        ActivityMetrics.activity_id == activity_id,
        ActivityMetrics.user_id == current_user.id,
        ActivityMetrics.threshold_method == threshold_method,
    )
    result = await db.execute(stmt)
    metrics = result.scalar_one_or_none()

    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metrics found for activity {activity_id}.",
        )

    response = ActivityMetricsResponse.model_validate(metrics)

    # Write to cache
    cache = _get_cache()
    try:
        await cache.set_json(cache_key, response.model_dump(mode="json"), METRICS_CACHE_TTL)
    finally:
        await cache.close()

    return response


# Keep the old /activity/{id} path as an alias for backwards compatibility
@router.get(
    "/activity/{activity_id}",
    response_model=ActivityMetricsResponse,
    summary="Get computed metrics for an activity (deprecated, use /activities/{id})",
    deprecated=True,
)
async def get_activity_metrics_legacy(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    threshold_method: str = Query(default="manual", description="Threshold method"),
) -> ActivityMetricsResponse:
    """Deprecated: use GET /metrics/activities/{activity_id} instead."""
    return await get_activity_metrics(activity_id, db, current_user, threshold_method)


@router.get(
    "/summary",
    response_model=PeriodSummary,
    summary="Get period summary (total TSS, rides, duration, distance)",
)
async def get_period_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    start_date: date | None = Query(default=None, description="Start date (default: 30 days ago)"),
    end_date: date | None = Query(default=None, description="End date (default: today)"),
) -> PeriodSummary:
    """Return aggregated summary metrics for all rides in a date range.

    Defaults to the last 30 days if no date range specified.
    """
    today = date.today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date",
        )

    # Check cache
    cache = _get_cache()
    cache_key = summary_cache_key(current_user.id, str(start_date), str(end_date))
    try:
        cached = await cache.get_json(cache_key)
        if cached is not None:
            logger.debug("cache_hit", key=cache_key)
            return PeriodSummary.model_validate(cached)
    finally:
        await cache.close()

    # Aggregate from activities table
    stmt = select(
        func.coalesce(func.sum(Activity.tss), Decimal("0")).label("total_tss"),
        func.count(Activity.id).label("ride_count"),
        func.coalesce(func.sum(Activity.duration_seconds), 0).label("total_duration_seconds"),
        func.coalesce(func.sum(Activity.distance_meters), Decimal("0")).label(
            "total_distance_meters"
        ),
    ).where(
        Activity.user_id == current_user.id,
        Activity.activity_date >= start_date,
        Activity.activity_date <= end_date,
    )

    result = await db.execute(stmt)
    row = result.one()

    response = PeriodSummary(
        total_tss=row.total_tss,
        ride_count=row.ride_count,
        total_duration_seconds=row.total_duration_seconds,
        total_distance_meters=row.total_distance_meters,
        start_date=start_date,
        end_date=end_date,
    )

    # Write to cache
    cache = _get_cache()
    try:
        await cache.set_json(cache_key, response.model_dump(mode="json"), SUMMARY_CACHE_TTL)
    finally:
        await cache.close()

    return response


# ---------------------------------------------------------------------------
# Power Analysis (Plan 7.2)
# ---------------------------------------------------------------------------


async def _get_activity_for_analysis(
    activity_id: int,
    db: AsyncSession,
    user_id: int,
) -> Activity:
    """Fetch activity for analysis, raising 404 if not found or not owned."""
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == user_id,
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
    "/activities/{activity_id}/power-analysis",
    response_model=PowerAnalysisResponse,
    summary="Get power analysis for an activity",
)
async def get_activity_power_analysis(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    ftp: int = Query(default=0, ge=0, description="FTP in watts (0 = use profile FTP)"),
) -> PowerAnalysisResponse:
    """Return power distribution, peak efforts, and advanced stats for an activity.

    If ftp=0, attempts to use the user's profile FTP.
    """
    activity = await _get_activity_for_analysis(activity_id, db, current_user.id)

    # Determine FTP
    effective_ftp = ftp
    if effective_ftp <= 0:
        # Try to get from user settings
        from app.models.user_settings import UserSettings

        settings_stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
        settings_result = await db.execute(settings_stmt)
        user_settings = settings_result.scalar_one_or_none()
        if user_settings and user_settings.ftp_watts:
            effective_ftp = int(user_settings.ftp_watts)
        else:
            effective_ftp = 200  # sensible default

    # Get weight from user settings
    weight_kg: float | None = None
    if hasattr(current_user, "weight_kg") and current_user.weight_kg:
        weight_kg = float(current_user.weight_kg)

    return await get_power_analysis(
        activity_id,
        effective_ftp,
        db,
        weight_kg=weight_kg,
        duration_seconds=activity.duration_seconds,
    )


# ---------------------------------------------------------------------------
# HR Analysis (Plan 7.3)
# ---------------------------------------------------------------------------


@router.get(
    "/activities/{activity_id}/hr-analysis",
    response_model=HRAnalysisResponse,
    summary="Get HR analysis for an activity",
)
async def get_activity_hr_analysis(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    max_hr: int = Query(default=190, gt=0, le=250, description="Max HR for zone calculation"),
) -> HRAnalysisResponse:
    """Return HR distribution, time-in-zones, and HR stats for an activity."""
    await _get_activity_for_analysis(activity_id, db, current_user.id)
    return await get_hr_analysis(activity_id, max_hr, db)
