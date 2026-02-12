"""Tests for the threshold estimation service -- Plans 4.2 and 4.3."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.threshold_service import (
    EIGHT_MIN_SECONDS,
    PCT_8MIN_FACTOR,
    PCT_20MIN_FACTOR,
    TWENTY_MIN_SECONDS,
    estimate_threshold_8min,
    estimate_threshold_20min,
    get_threshold_at_date,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_activity_row(
    activity_id: int,
    activity_date: datetime,
    duration_seconds: int,
) -> SimpleNamespace:
    """Create a fake activity row."""
    return SimpleNamespace(
        id=activity_id,
        activity_date=activity_date,
        duration_seconds=duration_seconds,
    )


def _make_stream_row(power_watts: int | None) -> SimpleNamespace:
    """Create a fake stream row with power data."""
    return SimpleNamespace(power_watts=power_watts)


def _build_mock_db_for_estimation(
    activities: list[SimpleNamespace],
    stream_data_by_activity: dict[int, list[SimpleNamespace]],
    existing_threshold: object = None,
) -> AsyncMock:
    """Build a mock DB for threshold estimation.

    The mock handles sequential calls:
    1. Activity list query
    2-N. Stream queries per activity
    N+1. Existing threshold check
    """
    db = AsyncMock()
    call_count = 0
    activity_stream_index = 0

    # Build ordered list of activity IDs for stream lookup
    activity_ids_in_order = [a.id for a in activities]

    async def fake_execute(stmt):
        nonlocal call_count, activity_stream_index
        call_count += 1
        mock_result = MagicMock()

        if call_count == 1:
            # Activity list query
            mock_result.fetchall.return_value = activities
        elif call_count <= 1 + len(activities):
            # Stream data queries (one per activity)
            idx = call_count - 2
            aid = activity_ids_in_order[idx]
            stream_rows = stream_data_by_activity.get(aid, [])
            mock_result.fetchall.return_value = stream_rows
        else:
            # Existing threshold check
            mock_result.scalar_one_or_none.return_value = existing_threshold

        return mock_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.add = MagicMock()
    db.flush = AsyncMock()

    return db


# ---------------------------------------------------------------------------
# Tests: estimate_threshold_20min
# ---------------------------------------------------------------------------


class TestEstimateThreshold20min:
    """Tests for the 20-minute FTP estimation method."""

    @pytest.mark.asyncio
    async def test_estimates_ftp_from_20min_effort(self) -> None:
        """Should estimate FTP as 95% of best 20-min power."""
        activity_date = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        activities = [
            _make_activity_row(1, activity_date, 3600),
        ]

        # 1200 samples of steady 300W (20 minutes)
        stream_data = {
            1: [_make_stream_row(300) for _ in range(TWENTY_MIN_SECONDS + 100)],
        }

        db = _build_mock_db_for_estimation(activities, stream_data)

        result = await estimate_threshold_20min(1, db)

        assert result is not None
        expected_ftp = (Decimal("300.0") * PCT_20MIN_FACTOR).quantize(Decimal("0.1"))
        assert result.ftp_watts == expected_ftp  # 285.0
        assert result.method == "pct_20min"
        assert result.source_activity_id == 1
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_no_qualifying_rides_returns_none(self) -> None:
        """No rides >= 20 minutes should return None."""
        # No activities match the duration filter
        db = _build_mock_db_for_estimation([], {})

        result = await estimate_threshold_20min(1, db)

        assert result is None

    @pytest.mark.asyncio
    async def test_picks_best_across_multiple_activities(self) -> None:
        """Should find the highest 20-min effort across all activities."""
        activities = [
            _make_activity_row(1, datetime(2026, 1, 10, 10, 0, tzinfo=UTC), 3600),
            _make_activity_row(2, datetime(2026, 1, 15, 10, 0, tzinfo=UTC), 3600),
        ]

        stream_data = {
            1: [_make_stream_row(250) for _ in range(TWENTY_MIN_SECONDS + 100)],
            2: [_make_stream_row(320) for _ in range(TWENTY_MIN_SECONDS + 100)],
        }

        db = _build_mock_db_for_estimation(activities, stream_data)

        result = await estimate_threshold_20min(1, db)

        assert result is not None
        # Best is 320W from activity 2
        expected_ftp = (Decimal("320.0") * PCT_20MIN_FACTOR).quantize(Decimal("0.1"))
        assert result.ftp_watts == expected_ftp  # 304.0
        assert result.source_activity_id == 2

    @pytest.mark.asyncio
    async def test_activity_with_no_stream_data_skipped(self) -> None:
        """Activities without stream data should be skipped."""
        activities = [
            _make_activity_row(1, datetime(2026, 1, 10, 10, 0, tzinfo=UTC), 3600),
        ]

        # No stream data for the activity
        stream_data: dict[int, list[SimpleNamespace]] = {1: []}

        db = _build_mock_db_for_estimation(activities, stream_data)

        result = await estimate_threshold_20min(1, db)

        assert result is None


# ---------------------------------------------------------------------------
# Tests: estimate_threshold_8min
# ---------------------------------------------------------------------------


class TestEstimateThreshold8min:
    """Tests for the 8-minute FTP estimation method."""

    @pytest.mark.asyncio
    async def test_estimates_ftp_from_8min_effort(self) -> None:
        """Should estimate FTP as 90% of best 8-min power."""
        activity_date = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        activities = [
            _make_activity_row(1, activity_date, 1200),
        ]

        stream_data = {
            1: [_make_stream_row(350) for _ in range(EIGHT_MIN_SECONDS + 100)],
        }

        db = _build_mock_db_for_estimation(activities, stream_data)

        result = await estimate_threshold_8min(1, db)

        assert result is not None
        expected_ftp = (Decimal("350.0") * PCT_8MIN_FACTOR).quantize(Decimal("0.1"))
        assert result.ftp_watts == expected_ftp  # 315.0
        assert result.method == "pct_8min"
        assert result.source_activity_id == 1

    @pytest.mark.asyncio
    async def test_no_qualifying_rides_returns_none(self) -> None:
        """No rides >= 8 minutes should return None."""
        db = _build_mock_db_for_estimation([], {})

        result = await estimate_threshold_8min(1, db)

        assert result is None

    @pytest.mark.asyncio
    async def test_8min_captures_shorter_rides_than_20min(self) -> None:
        """8-min method should work for 10-minute rides that are too short for 20-min."""
        activities = [
            _make_activity_row(1, datetime(2026, 1, 15, 10, 0, tzinfo=UTC), 600),
        ]

        # 600 samples (10 minutes) -- enough for 8-min but not 20-min
        stream_data = {
            1: [_make_stream_row(280) for _ in range(600)],
        }

        db = _build_mock_db_for_estimation(activities, stream_data)

        result = await estimate_threshold_8min(1, db)

        assert result is not None
        expected_ftp = (Decimal("280.0") * PCT_8MIN_FACTOR).quantize(Decimal("0.1"))
        assert result.ftp_watts == expected_ftp  # 252.0


# ---------------------------------------------------------------------------
# Tests: get_threshold_at_date
# ---------------------------------------------------------------------------


class TestGetThresholdAtDate:
    """Tests for historical threshold lookup."""

    @pytest.mark.asyncio
    async def test_returns_most_recent_threshold(self) -> None:
        """Should return the most recent active threshold before the target date."""
        threshold = SimpleNamespace(
            id=1,
            user_id=1,
            method="manual",
            ftp_watts=Decimal("280"),
            effective_date=date(2026, 1, 1),
            is_active=True,
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = threshold
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_threshold_at_date(1, "manual", date(2026, 1, 15), db)

        assert result is not None
        assert result.ftp_watts == Decimal("280")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_threshold(self) -> None:
        """Should return None when no threshold exists before the target date."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_threshold_at_date(1, "pct_20min", date(2026, 1, 15), db)

        assert result is None
