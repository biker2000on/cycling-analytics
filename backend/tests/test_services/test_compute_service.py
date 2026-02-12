"""Tests for the metric computation service — Plan 2.3."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.activity_metrics import ActivityMetrics
from app.models.user_settings import UserSettings
from app.services.compute_service import (
    DEFAULT_FTP,
    compute_activity_metrics,
    recompute_all_metrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_activity(
    activity_id: int = 1,
    user_id: int = 1,
    duration_seconds: int = 3600,
    avg_power_watts: Decimal | None = Decimal("200"),
    avg_hr: int | None = 150,
) -> Activity:
    """Create a minimal Activity object for testing."""
    a = Activity(
        id=activity_id,
        user_id=user_id,
        source=ActivitySource.fit_upload,
        activity_date=datetime(2025, 6, 1, 8, 0, tzinfo=UTC),
        name="Test Ride",
        duration_seconds=duration_seconds,
        avg_power_watts=avg_power_watts,
        avg_hr=avg_hr,
        processing_status=ProcessingStatus.complete,
    )
    return a


def _make_user_settings(user_id: int = 1, ftp_watts: Decimal | None = Decimal("280")) -> UserSettings:
    """Create a minimal UserSettings object."""
    s = UserSettings(
        id=1,
        user_id=user_id,
        ftp_watts=ftp_watts,
        ftp_method="manual",
    )
    return s


class _FakeRow:
    """Simulates a DB row with power_watts and heart_rate attributes."""

    def __init__(self, power_watts: int | None, heart_rate: int | None = None):
        self.power_watts = power_watts
        self.heart_rate = heart_rate


# ---------------------------------------------------------------------------
# Mock DB helper
# ---------------------------------------------------------------------------


def _build_mock_db(
    activity: Activity | None,
    user_settings: UserSettings | None,
    stream_rows: list[_FakeRow],
    existing_metrics: ActivityMetrics | None = None,
):
    """Build an AsyncMock db session with pre-programmed select results.

    The mock handles four sequential execute calls:
    1. Activity lookup
    2. UserSettings lookup
    3. Stream data lookup
    4. Existing ActivityMetrics lookup
    Then flush calls for upsert and activity update.
    """
    db = AsyncMock()
    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        call_count += 1

        mock_result = MagicMock()

        if call_count == 1:
            # Activity lookup
            mock_result.scalar_one_or_none.return_value = activity
        elif call_count == 2:
            # UserSettings lookup
            mock_result.scalar_one_or_none.return_value = user_settings
        elif call_count == 3:
            # Stream data — returns rows with .power_watts and .heart_rate
            mock_result.fetchall.return_value = stream_rows
        elif call_count == 4:
            # Existing ActivityMetrics lookup
            mock_result.scalar_one_or_none.return_value = existing_metrics
        else:
            # Activity summary update
            mock_result.scalar_one_or_none.return_value = None

        return mock_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.flush = AsyncMock()
    db.add = MagicMock()

    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeActivityMetrics:
    """Test compute_activity_metrics with various scenarios."""

    @pytest.mark.asyncio
    async def test_compute_with_stream_data(self) -> None:
        """Compute NP/IF/TSS from power stream data with known FTP."""
        activity = _make_activity(duration_seconds=3600)
        settings = _make_user_settings(ftp_watts=Decimal("200"))

        # Steady 200W for 5 minutes (enough for rolling average)
        stream_rows = [_FakeRow(200, 150) for _ in range(300)]

        db = _build_mock_db(activity, settings, stream_rows)

        result = await compute_activity_metrics(1, 1, db)

        assert result is not None
        assert result.ftp_at_computation == Decimal("200")
        assert result.normalized_power is not None
        # Steady 200W with FTP 200 => NP ~200, IF ~1.0, TSS ~100 for 1 hour
        assert abs(result.normalized_power - Decimal("200")) <= Decimal("2")
        assert result.intensity_factor is not None
        assert result.tss is not None
        assert result.variability_index is not None
        assert result.zone_distribution is not None

    @pytest.mark.asyncio
    async def test_compute_with_no_ftp_uses_default(self) -> None:
        """When user has no FTP set, use default (200W)."""
        activity = _make_activity(duration_seconds=300)
        stream_rows = [_FakeRow(200) for _ in range(300)]

        db = _build_mock_db(activity, None, stream_rows)

        result = await compute_activity_metrics(1, 1, db)

        assert result.ftp_at_computation == DEFAULT_FTP

    @pytest.mark.asyncio
    async def test_compute_manual_activity_no_streams(self) -> None:
        """Manual activity with avg_power but no streams uses estimation."""
        activity = _make_activity(
            duration_seconds=3600,
            avg_power_watts=Decimal("180"),
        )
        settings = _make_user_settings(ftp_watts=Decimal("200"))

        # No stream data
        db = _build_mock_db(activity, settings, [])

        result = await compute_activity_metrics(1, 1, db)

        assert result.normalized_power == Decimal("180")
        assert result.tss is not None
        assert result.intensity_factor is not None
        assert result.variability_index == Decimal("1.00")
        assert result.efficiency_factor is None  # no HR stream data

    @pytest.mark.asyncio
    async def test_compute_activity_not_found_raises(self) -> None:
        """Activity not found should raise ValueError."""
        db = _build_mock_db(None, None, [])

        with pytest.raises(ValueError, match="Activity 999 not found"):
            await compute_activity_metrics(999, 1, db)

    @pytest.mark.asyncio
    async def test_activity_summary_fields_updated(self) -> None:
        """Verify that activity summary fields (tss, np_watts, if) are updated."""
        activity = _make_activity(duration_seconds=3600)
        settings = _make_user_settings(ftp_watts=Decimal("200"))
        stream_rows = [_FakeRow(200, 150) for _ in range(300)]

        db = _build_mock_db(activity, settings, stream_rows)

        await compute_activity_metrics(1, 1, db)

        # The db.execute should have been called 5 times:
        # 1=activity, 2=settings, 3=streams, 4=existing metrics, 5=update activity
        assert db.execute.call_count == 5
        # flush should have been called twice (metrics upsert + activity update)
        assert db.flush.call_count == 2

    @pytest.mark.asyncio
    async def test_efficiency_factor_with_hr_data(self) -> None:
        """Efficiency factor should be computed when HR data is available."""
        activity = _make_activity(duration_seconds=300)
        settings = _make_user_settings(ftp_watts=Decimal("200"))
        stream_rows = [_FakeRow(200, 150) for _ in range(300)]

        db = _build_mock_db(activity, settings, stream_rows)

        result = await compute_activity_metrics(1, 1, db)

        assert result.efficiency_factor is not None
        # EF = NP / avg_HR ≈ 200 / 150 ≈ 1.33
        assert abs(result.efficiency_factor - Decimal("1.33")) <= Decimal("0.05")

    @pytest.mark.asyncio
    async def test_no_power_no_avg_returns_nulls(self) -> None:
        """Activity with no power data and no avg_power produces null metrics."""
        activity = _make_activity(avg_power_watts=None)
        settings = _make_user_settings(ftp_watts=Decimal("200"))

        db = _build_mock_db(activity, settings, [])

        result = await compute_activity_metrics(1, 1, db)

        assert result.normalized_power is None
        assert result.tss is None
        assert result.intensity_factor is None


class TestRecomputeAllMetrics:
    """Test recompute_all_metrics."""

    @pytest.mark.asyncio
    async def test_recompute_all_activities(self) -> None:
        """Recompute iterates over all activities for a user."""
        db = AsyncMock()

        # First call: fetch activity IDs
        ids_result = MagicMock()
        ids_result.fetchall.return_value = [(1,), (2,), (3,)]
        db.execute = AsyncMock(return_value=ids_result)

        with patch(
            "app.services.compute_service.compute_activity_metrics",
            new_callable=AsyncMock,
        ) as mock_compute:
            mock_compute.return_value = MagicMock()

            count = await recompute_all_metrics(1, db)

        assert count == 3
        assert mock_compute.call_count == 3

    @pytest.mark.asyncio
    async def test_recompute_handles_individual_failures(self) -> None:
        """Recompute continues if one activity fails."""
        db = AsyncMock()

        ids_result = MagicMock()
        ids_result.fetchall.return_value = [(1,), (2,), (3,)]
        db.execute = AsyncMock(return_value=ids_result)

        call_count = 0

        async def side_effect(aid, uid, session, method="manual"):
            nonlocal call_count
            call_count += 1
            if aid == 2:
                raise ValueError("Stream data corrupt")
            return MagicMock()

        with patch(
            "app.services.compute_service.compute_activity_metrics",
            new_callable=AsyncMock,
            side_effect=side_effect,
        ):
            count = await recompute_all_metrics(1, db)

        # 2 succeeded, 1 failed
        assert count == 2
