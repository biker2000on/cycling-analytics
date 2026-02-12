"""Tests for power analysis and HR analysis API endpoints (Phase 7)."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_db
from app.main import app as the_app
from app.schemas.metrics import (
    HRAnalysisResponse,
    HRDistributionBin,
    HRZoneTime,
    PeakEffort,
    PowerAnalysisResponse,
    PowerAnalysisStats,
    PowerDistributionBin,
)
from app.schemas.stream import ZoneBlock, ZoneBlocksResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    """Async HTTP test client using the global app instance."""
    transport = ASGITransport(app=the_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture(autouse=True)
def _clear_overrides() -> None:  # type: ignore[misc]
    """Ensure dependency overrides are cleared after each test."""
    yield  # type: ignore[misc]
    the_app.dependency_overrides.clear()


def _override_db(mock_db: AsyncMock) -> None:
    """Set a dependency override for the DB session."""

    async def _fake_get_db():  # type: ignore[no-untyped-def]
        yield mock_db

    the_app.dependency_overrides[get_db] = _fake_get_db


def _mock_activity(activity_id: int = 1) -> SimpleNamespace:
    """Create a fake Activity-like object."""
    return SimpleNamespace(
        id=activity_id,
        user_id=1,
        name="Morning Ride",
        sport_type="cycling",
        duration_seconds=3600,
    )


def _mock_user_settings(ftp: int = 250) -> SimpleNamespace:
    """Create a fake UserSettings-like object."""
    return SimpleNamespace(
        user_id=1,
        ftp_watts=ftp,
    )


# ---------------------------------------------------------------------------
# Tests: GET /activities/{id}/streams/zones
# ---------------------------------------------------------------------------


class TestGetStreamZones:
    """Tests for the zone blocks endpoint."""

    @pytest.mark.asyncio
    async def test_returns_zone_blocks(self, client: AsyncClient) -> None:
        """GET /activities/{id}/streams/zones returns zone blocks."""
        mock_response = ZoneBlocksResponse(
            activity_id=1,
            ftp=250,
            blocks=[
                ZoneBlock(start_seconds=0, end_seconds=30, zone=2, avg_power=Decimal("160")),
                ZoneBlock(start_seconds=30, end_seconds=60, zone=4, avg_power=Decimal("240")),
            ],
            total_blocks=2,
        )

        activity = _mock_activity()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = activity

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch(
            "app.routers.streams.get_zone_blocks",
            return_value=mock_response,
        ):
            resp = await client.get("/activities/1/streams/zones?ftp=250")

        assert resp.status_code == 200
        data = resp.json()
        assert data["activity_id"] == 1
        assert data["ftp"] == 250
        assert len(data["blocks"]) == 2
        assert data["blocks"][0]["zone"] == 2

    @pytest.mark.asyncio
    async def test_requires_ftp_parameter(self, client: AsyncClient) -> None:
        """GET /activities/{id}/streams/zones requires ftp query parameter."""
        resp = await client.get("/activities/1/streams/zones")
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_activity_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /activities/{id}/streams/zones returns 404 for missing activity."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        resp = await client.get("/activities/999/streams/zones?ftp=250")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET /metrics/activities/{id}/power-analysis
# ---------------------------------------------------------------------------


class TestGetPowerAnalysis:
    """Tests for the power analysis endpoint."""

    @pytest.mark.asyncio
    async def test_returns_power_analysis(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id}/power-analysis returns analysis data."""
        mock_response = PowerAnalysisResponse(
            activity_id=1,
            ftp=250,
            distribution=[
                PowerDistributionBin(bin_start=190, bin_end=200, count=100, zone=4),
            ],
            peak_efforts=[
                PeakEffort(
                    duration_seconds=5,
                    duration_label="5 sec",
                    power_watts=Decimal("350"),
                    power_wpkg=None,
                ),
            ],
            stats=PowerAnalysisStats(
                normalized_power=Decimal("220"),
                avg_power=Decimal("200"),
                max_power=350,
            ),
        )

        # Mock both execute calls (activity lookup + user settings lookup)
        activity = _mock_activity()
        settings = _mock_user_settings()
        call_count = 0

        mock_db = AsyncMock()

        def _make_result(obj: object) -> MagicMock:
            result = MagicMock()
            result.scalar_one_or_none.return_value = obj
            return result

        results = [_make_result(activity), _make_result(settings)]

        async def _fake_execute(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            idx = min(call_count, len(results) - 1)
            call_count += 1
            return results[idx]

        mock_db.execute = _fake_execute
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch(
            "app.routers.metrics.get_power_analysis",
            return_value=mock_response,
        ):
            resp = await client.get("/metrics/activities/1/power-analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert data["activity_id"] == 1
        assert len(data["distribution"]) >= 1
        assert len(data["peak_efforts"]) >= 1
        assert data["stats"]["normalized_power"] is not None

    @pytest.mark.asyncio
    async def test_activity_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id}/power-analysis returns 404 for missing activity."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        resp = await client.get("/metrics/activities/999/power-analysis")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET /metrics/activities/{id}/hr-analysis
# ---------------------------------------------------------------------------


class TestGetHRAnalysis:
    """Tests for the HR analysis endpoint."""

    @pytest.mark.asyncio
    async def test_returns_hr_analysis(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id}/hr-analysis returns HR analysis data."""
        mock_response = HRAnalysisResponse(
            activity_id=1,
            max_hr_setting=190,
            avg_hr=155,
            max_hr=180,
            min_hr=120,
            distribution=[
                HRDistributionBin(bin_start=150, bin_end=155, count=100),
            ],
            time_in_zones=[
                HRZoneTime(zone=1, name="Recovery", min_hr=0, max_hr=129, seconds=100),
                HRZoneTime(zone=2, name="Aerobic", min_hr=129, max_hr=156, seconds=200),
                HRZoneTime(zone=3, name="Tempo", min_hr=156, max_hr=165, seconds=150),
                HRZoneTime(zone=4, name="Threshold", min_hr=165, max_hr=175, seconds=100),
                HRZoneTime(zone=5, name="VO2max", min_hr=175, max_hr=190, seconds=50),
            ],
        )

        activity = _mock_activity()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = activity

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch(
            "app.routers.metrics.get_hr_analysis",
            return_value=mock_response,
        ):
            resp = await client.get("/metrics/activities/1/hr-analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert data["activity_id"] == 1
        assert data["avg_hr"] == 155
        assert len(data["distribution"]) >= 1
        assert len(data["time_in_zones"]) == 5

    @pytest.mark.asyncio
    async def test_custom_max_hr(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id}/hr-analysis accepts custom max_hr."""
        mock_response = HRAnalysisResponse(
            activity_id=1,
            max_hr_setting=200,
            avg_hr=155,
            max_hr=180,
            min_hr=120,
            distribution=[],
            time_in_zones=[
                HRZoneTime(zone=z, name=n, min_hr=0, max_hr=200, seconds=0)
                for z, n in [(1, "Recovery"), (2, "Aerobic"), (3, "Tempo"), (4, "Threshold"), (5, "VO2max")]
            ],
        )

        activity = _mock_activity()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = activity

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch(
            "app.routers.metrics.get_hr_analysis",
            return_value=mock_response,
        ):
            resp = await client.get("/metrics/activities/1/hr-analysis?max_hr=200")

        assert resp.status_code == 200
        data = resp.json()
        assert data["max_hr_setting"] == 200

    @pytest.mark.asyncio
    async def test_activity_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id}/hr-analysis returns 404 for missing activity."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        resp = await client.get("/metrics/activities/999/hr-analysis")
        assert resp.status_code == 404
