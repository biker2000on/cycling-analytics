"""Tests for totals service (Plan 8.4)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.totals_service import (
    _generate_monthly_periods,
    _generate_weekly_periods,
    _generate_yearly_periods,
    get_totals,
)


class TestGenerateWeeklyPeriods:
    """Tests for weekly period generation."""

    def test_single_week(self) -> None:
        """A single week should produce one period."""
        periods = _generate_weekly_periods(date(2024, 1, 1), date(2024, 1, 7))
        assert len(periods) >= 1
        label, start, end = periods[0]
        assert "W" in label
        # Monday of the week containing Jan 1, 2024
        assert start.weekday() == 0  # Monday

    def test_multiple_weeks(self) -> None:
        """Multiple weeks should produce one period per week."""
        periods = _generate_weekly_periods(date(2024, 1, 1), date(2024, 1, 28))
        assert len(periods) >= 4

    def test_periods_are_sequential(self) -> None:
        """Periods should be chronologically ordered."""
        periods = _generate_weekly_periods(date(2024, 1, 1), date(2024, 3, 31))
        for i in range(len(periods) - 1):
            assert periods[i][1] < periods[i + 1][1]


class TestGenerateMonthlyPeriods:
    """Tests for monthly period generation."""

    def test_single_month(self) -> None:
        """A single month should produce one period."""
        periods = _generate_monthly_periods(date(2024, 3, 1), date(2024, 3, 31))
        assert len(periods) == 1
        assert periods[0][0] == "Mar 2024"

    def test_multiple_months(self) -> None:
        """Multiple months should produce one period per month."""
        periods = _generate_monthly_periods(date(2024, 1, 1), date(2024, 6, 30))
        assert len(periods) == 6

    def test_cross_year_boundary(self) -> None:
        """Should handle year boundaries."""
        periods = _generate_monthly_periods(date(2023, 11, 1), date(2024, 2, 29))
        assert len(periods) == 4
        labels = [p[0] for p in periods]
        assert "Nov 2023" in labels
        assert "Feb 2024" in labels


class TestGenerateYearlyPeriods:
    """Tests for yearly period generation."""

    def test_single_year(self) -> None:
        """A single year should produce one period."""
        periods = _generate_yearly_periods(date(2024, 1, 1), date(2024, 12, 31))
        assert len(periods) == 1
        assert periods[0][0] == "2024"

    def test_multiple_years(self) -> None:
        """Multiple years should produce one period per year."""
        periods = _generate_yearly_periods(date(2022, 1, 1), date(2024, 12, 31))
        assert len(periods) == 3


class TestGetTotals:
    """Tests for the get_totals function."""

    @pytest.mark.asyncio
    async def test_returns_empty_periods(self) -> None:
        """Should return periods even when no activities exist."""
        # Mock DB returning zero for all aggregates
        mock_row = MagicMock()
        mock_row.ride_count = 0
        mock_row.total_tss = Decimal("0")
        mock_row.total_duration_seconds = 0
        mock_row.total_distance_meters = Decimal("0")

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await get_totals(
            user_id=1,
            period_type="weekly",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 28),
            db=db,
        )

        assert result.period_type == "weekly"
        assert len(result.periods) >= 4
        for p in result.periods:
            assert p.ride_count == 0

    @pytest.mark.asyncio
    async def test_monthly_periods_structure(self) -> None:
        """Monthly totals should have correct structure."""
        mock_row = MagicMock()
        mock_row.ride_count = 5
        mock_row.total_tss = Decimal("350.0")
        mock_row.total_duration_seconds = 18000
        mock_row.total_distance_meters = Decimal("250000.0")

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await get_totals(
            user_id=1,
            period_type="monthly",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            db=db,
        )

        assert result.period_type == "monthly"
        assert len(result.periods) == 3
        for p in result.periods:
            assert p.ride_count == 5
            assert p.total_tss == Decimal("350.0")
