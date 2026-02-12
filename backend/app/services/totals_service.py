"""Totals service -- aggregate activity metrics by period (weekly/monthly/yearly).

Queries the Activity table with date grouping to produce period-level summaries.
"""

from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.schemas.metrics import TotalsPeriod, TotalsResponse

logger = structlog.get_logger(__name__)


def _week_boundaries(d: date) -> tuple[date, date]:
    """Return Monday and Sunday of the week containing date d."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _generate_weekly_periods(start_date: date, end_date: date) -> list[tuple[str, date, date]]:
    """Generate weekly period labels and boundaries."""
    periods: list[tuple[str, date, date]] = []
    current = start_date - timedelta(days=start_date.weekday())  # Start of week
    while current <= end_date:
        week_end = current + timedelta(days=6)
        iso_year, iso_week, _ = current.isocalendar()
        label = f"{iso_year}-W{iso_week:02d}"
        periods.append((label, current, min(week_end, end_date)))
        current += timedelta(weeks=1)
    return periods


def _generate_monthly_periods(start_date: date, end_date: date) -> list[tuple[str, date, date]]:
    """Generate monthly period labels and boundaries."""
    import calendar

    periods: list[tuple[str, date, date]] = []
    current_year = start_date.year
    current_month = start_date.month

    while date(current_year, current_month, 1) <= end_date:
        month_start = date(current_year, current_month, 1)
        last_day = calendar.monthrange(current_year, current_month)[1]
        month_end = date(current_year, current_month, last_day)
        label = month_start.strftime("%b %Y")
        periods.append((label, month_start, min(month_end, end_date)))

        # Advance
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return periods


def _generate_yearly_periods(start_date: date, end_date: date) -> list[tuple[str, date, date]]:
    """Generate yearly period labels and boundaries."""
    periods: list[tuple[str, date, date]] = []
    for year in range(start_date.year, end_date.year + 1):
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        periods.append((str(year), max(year_start, start_date), min(year_end, end_date)))
    return periods


async def get_totals(
    user_id: int,
    period_type: str,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> TotalsResponse:
    """Compute aggregated totals grouped by the specified period type."""
    # Generate period boundaries
    if period_type == "weekly":
        period_defs = _generate_weekly_periods(start_date, end_date)
    elif period_type == "monthly":
        period_defs = _generate_monthly_periods(start_date, end_date)
    else:
        period_defs = _generate_yearly_periods(start_date, end_date)

    # For each period, query aggregates
    periods: list[TotalsPeriod] = []
    for label, p_start, p_end in period_defs:
        stmt = select(
            func.count(Activity.id).label("ride_count"),
            func.coalesce(func.sum(Activity.tss), Decimal("0")).label("total_tss"),
            func.coalesce(func.sum(Activity.duration_seconds), 0).label("total_duration_seconds"),
            func.coalesce(func.sum(Activity.distance_meters), Decimal("0")).label("total_distance_meters"),
        ).where(
            Activity.user_id == user_id,
            Activity.activity_date >= p_start,
            Activity.activity_date <= p_end,
        )

        result = await db.execute(stmt)
        row = result.one()

        periods.append(TotalsPeriod(
            period_label=label,
            period_start=p_start,
            period_end=p_end,
            ride_count=row.ride_count,
            total_tss=row.total_tss,
            total_duration_seconds=row.total_duration_seconds,
            total_distance_meters=row.total_distance_meters,
        ))

    return TotalsResponse(
        periods=periods,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
    )
