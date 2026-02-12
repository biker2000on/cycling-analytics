"""Tests for multi-method metric computation -- Plan 4.4."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.activity_metrics import ActivityMetrics
from app.models.user_settings import UserSettings
from app.services.compute_service import (
    compute_activity_metrics,
    compute_activity_metrics_all_methods,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_activity(
    activity_id: int = 1,
    user_id: int = 1,
    duration_seconds: int = 3600,
    avg_power_watts: Decimal | None = Decimal("200"),
) -> Activity:
    """Create a minimal Activity object for testing."""
    a = Activity(
        id=activity_id,
        user_id=user_id,
        source=ActivitySource.fit_upload,
        activity_date=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        name="Test Ride",
        duration_seconds=duration_seconds,
        avg_power_watts=avg_power_watts,
        processing_status=ProcessingStatus.complete,
    )
    return a


def _make_user_settings(ftp_watts: Decimal = Decimal("280")) -> UserSettings:
    """Create a minimal UserSettings object."""
    return UserSettings(
        id=1,
        user_id=1,
        ftp_watts=ftp_watts,
        ftp_method="manual",
    )


class _FakeRow:
    """Simulates a DB row with power_watts and heart_rate attributes."""

    def __init__(self, power_watts: int | None, heart_rate: int | None = None):
        self.power_watts = power_watts
        self.heart_rate = heart_rate


def _make_threshold(method: str, ftp_watts: Decimal) -> SimpleNamespace:
    """Create a fake Threshold object."""
    return SimpleNamespace(
        id=1,
        user_id=1,
        method=method,
        ftp_watts=ftp_watts,
        effective_date=datetime(2026, 1, 1).date(),
        source_activity_id=None,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Tests: compute_activity_metrics with non-manual method
# ---------------------------------------------------------------------------


class TestComputeWithThresholdMethod:
    """Test computing metrics with different threshold methods."""

    @pytest.mark.asyncio
    async def test_manual_method_uses_user_settings_ftp(self) -> None:
        """Manual method should use FTP from user_settings."""
        activity = _make_activity(duration_seconds=300)
        settings = _make_user_settings(ftp_watts=Decimal("250"))
        stream_rows = [_FakeRow(200, 150) for _ in range(300)]

        db = AsyncMock()
        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = activity
            elif call_count == 2:
                mock_result.scalar_one_or_none.return_value = settings
            elif call_count == 3:
                mock_result.fetchall.return_value = stream_rows
            elif call_count == 4:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        db.execute = AsyncMock(side_effect=fake_execute)
        db.flush = AsyncMock()
        db.add = MagicMock()

        result = await compute_activity_metrics(1, 1, db, threshold_method="manual")

        assert result.ftp_at_computation == Decimal("250")
        assert result.threshold_method == "manual"

    @pytest.mark.asyncio
    async def test_pct_20min_method_uses_threshold_table(self) -> None:
        """pct_20min method should look up FTP from thresholds table."""
        activity = _make_activity(duration_seconds=300)
        threshold = _make_threshold("pct_20min", Decimal("290"))
        stream_rows = [_FakeRow(200, 150) for _ in range(300)]

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
                # Threshold lookup (via get_threshold_at_date)
                mock_result.scalar_one_or_none.return_value = threshold
            elif call_count == 3:
                # Stream data
                mock_result.fetchall.return_value = stream_rows
            elif call_count == 4:
                # Existing metrics check
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        db.execute = AsyncMock(side_effect=fake_execute)
        db.flush = AsyncMock()
        db.add = MagicMock()

        result = await compute_activity_metrics(1, 1, db, threshold_method="pct_20min")

        assert result.ftp_at_computation == Decimal("290")
        assert result.threshold_method == "pct_20min"

    @pytest.mark.asyncio
    async def test_different_ftp_produces_different_metrics(self) -> None:
        """Different FTP values should produce different IF and TSS."""
        activity_low_ftp = _make_activity(duration_seconds=300)
        activity_high_ftp = _make_activity(duration_seconds=300)
        stream_rows = [_FakeRow(200, 150) for _ in range(300)]

        # Low FTP scenario
        settings_low = _make_user_settings(ftp_watts=Decimal("200"))
        db_low = AsyncMock()
        call_count_low = 0

        async def fake_execute_low(stmt):
            nonlocal call_count_low
            call_count_low += 1
            mock_result = MagicMock()
            if call_count_low == 1:
                mock_result.scalar_one_or_none.return_value = activity_low_ftp
            elif call_count_low == 2:
                mock_result.scalar_one_or_none.return_value = settings_low
            elif call_count_low == 3:
                mock_result.fetchall.return_value = stream_rows
            elif call_count_low == 4:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        db_low.execute = AsyncMock(side_effect=fake_execute_low)
        db_low.flush = AsyncMock()
        db_low.add = MagicMock()

        result_low = await compute_activity_metrics(1, 1, db_low, threshold_method="manual")

        # High FTP scenario
        settings_high = _make_user_settings(ftp_watts=Decimal("300"))
        db_high = AsyncMock()
        call_count_high = 0

        async def fake_execute_high(stmt):
            nonlocal call_count_high
            call_count_high += 1
            mock_result = MagicMock()
            if call_count_high == 1:
                mock_result.scalar_one_or_none.return_value = activity_high_ftp
            elif call_count_high == 2:
                mock_result.scalar_one_or_none.return_value = settings_high
            elif call_count_high == 3:
                mock_result.fetchall.return_value = stream_rows
            elif call_count_high == 4:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        db_high.execute = AsyncMock(side_effect=fake_execute_high)
        db_high.flush = AsyncMock()
        db_high.add = MagicMock()

        result_high = await compute_activity_metrics(1, 1, db_high, threshold_method="manual")

        # With lower FTP, IF and TSS should be higher (same power, lower FTP = harder)
        assert result_low.intensity_factor is not None
        assert result_high.intensity_factor is not None
        assert result_low.intensity_factor > result_high.intensity_factor

        assert result_low.tss is not None
        assert result_high.tss is not None
        assert result_low.tss > result_high.tss


# ---------------------------------------------------------------------------
# Tests: compute_activity_metrics_all_methods
# ---------------------------------------------------------------------------


class TestComputeAllMethods:
    """Tests for computing metrics across all available threshold methods."""

    @pytest.mark.asyncio
    async def test_computes_for_all_available_methods(self) -> None:
        """Should compute metrics for manual plus any auto-detected methods."""
        activity = _make_activity()

        with patch(
            "app.services.compute_service.compute_activity_metrics",
            new_callable=AsyncMock,
        ) as mock_compute:
            mock_compute.return_value = MagicMock(spec=ActivityMetrics)

            # Mock the activity lookup
            db = AsyncMock()
            activity_result = MagicMock()
            activity_result.scalar_one_or_none.return_value = activity
            db.execute = AsyncMock(return_value=activity_result)

            # Mock _get_ftp_for_method
            with patch(
                "app.services.compute_service._get_ftp_for_method",
                new_callable=AsyncMock,
            ) as mock_get_ftp:
                # manual always available, pct_20min available, pct_8min not available
                async def ftp_side_effect(uid, method, date, session):
                    if method == "manual":
                        return Decimal("250")
                    elif method == "pct_20min":
                        return Decimal("280")
                    elif method == "pct_8min":
                        return None
                    return None

                mock_get_ftp.side_effect = ftp_side_effect

                results = await compute_activity_metrics_all_methods(1, 1, db)

            # Should have computed for manual and pct_20min (2 methods)
            assert mock_compute.call_count == 2
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_activity_not_found_raises(self) -> None:
        """Should raise ValueError when activity not found."""
        db = AsyncMock()
        activity_result = MagicMock()
        activity_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=activity_result)

        with pytest.raises(ValueError, match="Activity 999 not found"):
            await compute_activity_metrics_all_methods(999, 1, db)

    @pytest.mark.asyncio
    async def test_handles_individual_method_failure(self) -> None:
        """Should continue computing other methods if one fails."""
        activity = _make_activity()

        call_idx = 0

        async def compute_side_effect(aid, uid, session, threshold_method="manual"):
            nonlocal call_idx
            call_idx += 1
            if threshold_method == "pct_20min":
                raise ValueError("Threshold computation error")
            return MagicMock(spec=ActivityMetrics)

        with patch(
            "app.services.compute_service.compute_activity_metrics",
            new_callable=AsyncMock,
            side_effect=compute_side_effect,
        ):
            db = AsyncMock()
            activity_result = MagicMock()
            activity_result.scalar_one_or_none.return_value = activity
            db.execute = AsyncMock(return_value=activity_result)

            with patch(
                "app.services.compute_service._get_ftp_for_method",
                new_callable=AsyncMock,
                return_value=Decimal("250"),
            ):
                results = await compute_activity_metrics_all_methods(1, 1, db)

            # manual succeeds, pct_20min fails, pct_8min succeeds = 2 results
            assert len(results) == 2
