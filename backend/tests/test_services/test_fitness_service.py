"""Tests for the fitness tracking service — Plan 2.4."""

from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.fitness_metrics import DailyFitness
from app.services.fitness_service import rebuild_fitness_history, update_fitness_from_date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTSSRow:
    """Simulates a DB row from the TSS aggregation query."""

    def __init__(self, activity_day: date, tss_total: Decimal, activity_count: int):
        self.activity_day = activity_day
        self.tss_total = tss_total
        self.activity_count = activity_count


def _build_fitness_service_db(
    prev_fitness: DailyFitness | None,
    tss_rows: list[_FakeTSSRow],
    existing_daily: list[DailyFitness] | None = None,
):
    """Build a mock async DB session for fitness service tests.

    Handles the sequential execute calls:
    1. Previous day's DailyFitness lookup
    2. TSS aggregation query
    3+. Per-day existing DailyFitness lookups
    """
    db = AsyncMock()
    call_count = 0
    existing_map = {}
    if existing_daily:
        for df in existing_daily:
            existing_map[df.date] = df

    # Track how many days we've looked up
    day_lookup_count = 0

    async def fake_execute(stmt):
        nonlocal call_count, day_lookup_count
        call_count += 1

        mock_result = MagicMock()

        if call_count == 1:
            # Previous day's DailyFitness
            mock_result.scalar_one_or_none.return_value = prev_fitness
        elif call_count == 2:
            # TSS aggregation query
            mock_result.fetchall.return_value = tss_rows
        else:
            # Per-day existing DailyFitness lookup
            mock_result.scalar_one_or_none.return_value = None

        return mock_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.flush = AsyncMock()
    db.add = MagicMock()

    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateFitnessFromDate:
    """Test update_fitness_from_date service function."""

    @pytest.mark.asyncio
    async def test_update_from_date_with_tss_data(self) -> None:
        """Basic update with known TSS data should create daily fitness rows."""
        from_date = date(2025, 6, 1)

        tss_rows = [
            _FakeTSSRow(date(2025, 6, 1), Decimal("80"), 1),
            _FakeTSSRow(date(2025, 6, 3), Decimal("120"), 2),
        ]

        db = _build_fitness_service_db(None, tss_rows)

        with patch("app.services.fitness_service.date") as mock_date_module:
            # We need to mock date.today() — but fitness_service uses datetime.date
            # So we'll patch the module-level function instead
            pass

        # Patch date.today to return a fixed date
        today = date(2025, 6, 5)
        with patch("app.services.fitness_service.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            count = await update_fitness_from_date(1, from_date, db)

        # Should update 5 days (June 1-5)
        assert count == 5
        # db.add should have been called 5 times (one per day)
        assert db.add.call_count == 5

    @pytest.mark.asyncio
    async def test_update_with_previous_fitness(self) -> None:
        """Update should use previous day's CTL/ATL as initial values."""
        from_date = date(2025, 6, 10)

        prev = DailyFitness(
            user_id=1,
            date=date(2025, 6, 9),
            threshold_method="manual",
            tss_total=Decimal("0"),
            ctl=Decimal("50"),
            atl=Decimal("40"),
            tsb=Decimal("10"),
            activity_count=0,
        )

        tss_rows = [
            _FakeTSSRow(date(2025, 6, 10), Decimal("100"), 1),
        ]

        db = _build_fitness_service_db(prev, tss_rows)

        today = date(2025, 6, 10)
        with patch("app.services.fitness_service.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            count = await update_fitness_from_date(1, from_date, db)

        assert count == 1

    @pytest.mark.asyncio
    async def test_future_date_returns_zero(self) -> None:
        """If from_date is in the future, return 0."""
        future = date(2099, 1, 1)
        db = AsyncMock()

        count = await update_fitness_from_date(1, future, db)
        assert count == 0


class TestRebuildFitnessHistory:
    """Test rebuild_fitness_history."""

    @pytest.mark.asyncio
    async def test_rebuild_with_no_activities(self) -> None:
        """Rebuild with no activities should return 0."""
        db = AsyncMock()

        # earliest activity query returns None
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        count = await rebuild_fitness_history(1, db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_rebuild_calls_update(self) -> None:
        """Rebuild should delete existing data and call update_fitness_from_date."""
        db = AsyncMock()

        earliest = datetime(2025, 1, 1, tzinfo=UTC)

        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()

            if call_count == 1:
                # earliest activity query
                mock_result.scalar_one_or_none.return_value = earliest
            elif call_count == 2:
                # delete statement
                pass
            else:
                # update_fitness_from_date internals
                mock_result.scalar_one_or_none.return_value = None
                mock_result.fetchall.return_value = []

            return mock_result

        db.execute = AsyncMock(side_effect=fake_execute)
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch(
            "app.services.fitness_service.update_fitness_from_date",
            new_callable=AsyncMock,
            return_value=365,
        ) as mock_update:
            count = await rebuild_fitness_history(1, db)

        assert count == 365
        mock_update.assert_called_once()
