"""Tests for power curve service (Plan 8.2)."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.power_curve_service import (
    STANDARD_DURATIONS,
    compute_power_curve,
)


def _make_activity(activity_id: int, activity_date: date) -> dict:
    return {
        "activity_id": activity_id,
        "activity_date": datetime(
            activity_date.year,
            activity_date.month,
            activity_date.day,
            tzinfo=timezone.utc,
        ),
    }


class TestComputePowerCurve:
    """Tests for power curve computation."""

    @pytest.mark.asyncio
    async def test_empty_when_no_activities(self) -> None:
        """No activities returns empty data."""
        db = AsyncMock()
        with patch(
            "app.services.power_curve_service._fetch_activities_with_power",
            return_value=[],
        ):
            result = await compute_power_curve(
                user_id=1,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 3, 31),
                db=db,
            )
        assert result.data == []
        assert result.start_date == date(2024, 1, 1)
        assert result.end_date == date(2024, 3, 31)

    @pytest.mark.asyncio
    async def test_single_activity_power_curve(self) -> None:
        """Power curve from a single activity with steady power."""
        db = AsyncMock()
        activity = _make_activity(1, date(2024, 2, 15))

        # 600 seconds at 200W
        power_stream = [200] * 600

        with (
            patch(
                "app.services.power_curve_service._fetch_activities_with_power",
                return_value=[activity],
            ),
            patch(
                "app.services.power_curve_service._fetch_power_stream",
                return_value=power_stream,
            ),
        ):
            result = await compute_power_curve(
                user_id=1,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 3, 31),
                db=db,
            )

        assert len(result.data) > 0

        # All durations up to 600s should have 200W
        for point in result.data:
            if point.duration_seconds <= 600:
                assert float(point.power_watts) == pytest.approx(200.0, abs=1)
                assert point.activity_id == 1

    @pytest.mark.asyncio
    async def test_best_effort_across_activities(self) -> None:
        """Power curve picks the best effort from any activity."""
        db = AsyncMock()

        act1 = _make_activity(1, date(2024, 2, 10))
        act2 = _make_activity(2, date(2024, 2, 20))

        # Activity 1: 300 seconds at 150W
        power_stream_1 = [150] * 300
        # Activity 2: 300 seconds at 250W (better)
        power_stream_2 = [250] * 300

        call_count = 0

        async def mock_fetch_power(activity_id, db):
            nonlocal call_count
            call_count += 1
            if activity_id == 1:
                return power_stream_1
            return power_stream_2

        with (
            patch(
                "app.services.power_curve_service._fetch_activities_with_power",
                return_value=[act1, act2],
            ),
            patch(
                "app.services.power_curve_service._fetch_power_stream",
                side_effect=mock_fetch_power,
            ),
        ):
            result = await compute_power_curve(
                user_id=1,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 3, 31),
                db=db,
            )

        # 5s effort should come from activity 2 (250W > 150W)
        point_5s = next((p for p in result.data if p.duration_seconds == 5), None)
        assert point_5s is not None
        assert float(point_5s.power_watts) == pytest.approx(250.0, abs=1)
        assert point_5s.activity_id == 2

    @pytest.mark.asyncio
    async def test_no_data_beyond_activity_length(self) -> None:
        """Durations longer than activity data should not appear."""
        db = AsyncMock()
        activity = _make_activity(1, date(2024, 2, 15))

        # Only 10 seconds of data
        power_stream = [300] * 10

        with (
            patch(
                "app.services.power_curve_service._fetch_activities_with_power",
                return_value=[activity],
            ),
            patch(
                "app.services.power_curve_service._fetch_power_stream",
                return_value=power_stream,
            ),
        ):
            result = await compute_power_curve(
                user_id=1,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 3, 31),
                db=db,
            )

        # Should only have points for durations <= 10
        for point in result.data:
            assert point.duration_seconds <= 10

    @pytest.mark.asyncio
    async def test_activity_with_no_valid_power(self) -> None:
        """Activity with all None power should not produce points."""
        db = AsyncMock()
        activity = _make_activity(1, date(2024, 2, 15))

        power_stream: list[int | None] = [None] * 100

        with (
            patch(
                "app.services.power_curve_service._fetch_activities_with_power",
                return_value=[activity],
            ),
            patch(
                "app.services.power_curve_service._fetch_power_stream",
                return_value=power_stream,
            ),
        ):
            result = await compute_power_curve(
                user_id=1,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 3, 31),
                db=db,
            )

        assert len(result.data) == 0


class TestStandardDurations:
    """Tests for the standard durations list."""

    def test_durations_are_sorted(self) -> None:
        """Durations should be in ascending order."""
        for i in range(len(STANDARD_DURATIONS) - 1):
            assert STANDARD_DURATIONS[i] < STANDARD_DURATIONS[i + 1]

    def test_includes_key_durations(self) -> None:
        """Key cycling durations should be included."""
        key = [1, 5, 30, 60, 300, 600, 1200, 1800, 3600]
        for d in key:
            assert d in STANDARD_DURATIONS
