"""Tests for the metrics API endpoints — Plan 2.5."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_db
from app.main import app as the_app


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


def _disable_cache() -> MagicMock:
    """Create a mock CacheService that always misses (returns None).

    Returns the mock so tests can assert cache interactions.
    """
    mock_cache = MagicMock()
    mock_cache.get_json = AsyncMock(return_value=None)
    mock_cache.set_json = AsyncMock()
    mock_cache.close = AsyncMock()
    return mock_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fitness_row(
    d: date,
    tss: Decimal = Decimal("80"),
    ctl: Decimal = Decimal("60"),
    atl: Decimal = Decimal("70"),
    tsb: Decimal = Decimal("-10"),
) -> SimpleNamespace:
    """Create a fake DailyFitness-like row."""
    return SimpleNamespace(
        user_id=1,
        date=d,
        threshold_method="manual",
        tss_total=tss,
        ctl=ctl,
        atl=atl,
        tsb=tsb,
    )


def _make_activity_metrics_row(
    activity_id: int = 1,
    tss: Decimal = Decimal("85.2"),
) -> SimpleNamespace:
    """Create a fake ActivityMetrics-like row."""
    return SimpleNamespace(
        activity_id=activity_id,
        user_id=1,
        normalized_power=Decimal("220"),
        tss=tss,
        intensity_factor=Decimal("0.92"),
        zone_distribution={"zone_seconds": {"z1": 100, "z2": 200}, "total_seconds": 300},
        variability_index=Decimal("1.05"),
        efficiency_factor=Decimal("1.47"),
        ftp_at_computation=Decimal("240"),
        threshold_method="manual",
        computed_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
    )


def _make_summary_row(
    total_tss: Decimal = Decimal("340.5"),
    ride_count: int = 4,
    total_duration: int = 14400,
    total_distance: Decimal = Decimal("200000"),
) -> SimpleNamespace:
    """Create a fake aggregation row for period summary."""
    return SimpleNamespace(
        total_tss=total_tss,
        ride_count=ride_count,
        total_duration_seconds=total_duration,
        total_distance_meters=total_distance,
    )


# ---------------------------------------------------------------------------
# Tests: GET /metrics/fitness
# ---------------------------------------------------------------------------


class TestGetFitness:
    """Tests for the fitness time series endpoint."""

    @pytest.mark.asyncio
    async def test_returns_fitness_data(self, client: AsyncClient) -> None:
        """GET /metrics/fitness returns fitness time series data."""
        rows = [
            _make_fitness_row(date(2026, 1, 1)),
            _make_fitness_row(date(2026, 1, 2)),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get(
                "/metrics/fitness?start_date=2026-01-01&end_date=2026-01-31"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["start_date"] == "2026-01-01"
        assert data["end_date"] == "2026-01-31"
        assert len(data["data"]) == 2
        assert data["data"][0]["ctl"] is not None

    @pytest.mark.asyncio
    async def test_fitness_date_range_validation(self, client: AsyncClient) -> None:
        """GET /metrics/fitness rejects start_date > end_date."""
        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get(
                "/metrics/fitness?start_date=2026-06-01&end_date=2026-01-01"
            )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_fitness_default_date_range(self, client: AsyncClient) -> None:
        """GET /metrics/fitness without dates defaults to last 90 days."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get("/metrics/fitness")

        assert response.status_code == 200
        data = response.json()
        assert data["threshold_method"] == "manual"
        assert len(data["data"]) == 0

    @pytest.mark.asyncio
    async def test_fitness_cache_hit_skips_db(self, client: AsyncClient) -> None:
        """When cache has data, DB is not queried."""
        cached_data = {
            "data": [
                {
                    "date": "2026-01-01",
                    "tss_total": "80",
                    "ctl": "60",
                    "atl": "70",
                    "tsb": "-10",
                }
            ],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "threshold_method": "manual",
        }
        mock_cache = MagicMock()
        mock_cache.get_json = AsyncMock(return_value=cached_data)
        mock_cache.set_json = AsyncMock()
        mock_cache.close = AsyncMock()

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get(
                "/metrics/fitness?start_date=2026-01-01&end_date=2026-01-31"
            )

        assert response.status_code == 200
        # DB should NOT have been called (cache hit)
        mock_db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests: GET /metrics/activities/{id}
# ---------------------------------------------------------------------------


class TestGetActivityMetrics:
    """Tests for the per-activity metrics endpoint."""

    @pytest.mark.asyncio
    async def test_returns_activity_metrics(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id} returns computed metrics."""
        metrics_row = _make_activity_metrics_row(activity_id=42)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = metrics_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get("/metrics/activities/42")

        assert response.status_code == 200
        data = response.json()
        assert data["activity_id"] == 42
        assert data["normalized_power"] is not None
        assert data["tss"] is not None
        assert data["threshold_method"] == "manual"

    @pytest.mark.asyncio
    async def test_activity_metrics_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id} returns 404 when no metrics exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get("/metrics/activities/99999")

        assert response.status_code == 404
        assert "No metrics found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_activity_metrics_cache_hit(self, client: AsyncClient) -> None:
        """When cache has activity metrics, DB is not queried."""
        cached_data = {
            "activity_id": 42,
            "normalized_power": "220",
            "tss": "85.2",
            "intensity_factor": "0.92",
            "zone_distribution": None,
            "variability_index": "1.05",
            "efficiency_factor": "1.47",
            "ftp_at_computation": "240",
            "threshold_method": "manual",
            "computed_at": "2026-02-10T12:00:00Z",
        }
        mock_cache = MagicMock()
        mock_cache.get_json = AsyncMock(return_value=cached_data)
        mock_cache.set_json = AsyncMock()
        mock_cache.close = AsyncMock()

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get("/metrics/activities/42")

        assert response.status_code == 200
        mock_db.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests: GET /metrics/activity/{id} (legacy)
# ---------------------------------------------------------------------------


class TestGetActivityMetricsLegacy:
    """Tests for the deprecated legacy endpoint."""

    @pytest.mark.asyncio
    async def test_legacy_endpoint_still_works(self, client: AsyncClient) -> None:
        """GET /metrics/activity/{id} still returns metrics (backwards compat)."""
        metrics_row = _make_activity_metrics_row(activity_id=7)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = metrics_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get("/metrics/activity/7")

        assert response.status_code == 200
        data = response.json()
        assert data["activity_id"] == 7


# ---------------------------------------------------------------------------
# Tests: GET /metrics/summary
# ---------------------------------------------------------------------------


class TestGetPeriodSummary:
    """Tests for the period summary endpoint."""

    @pytest.mark.asyncio
    async def test_returns_period_summary(self, client: AsyncClient) -> None:
        """GET /metrics/summary returns aggregated metrics."""
        summary_row = _make_summary_row()

        mock_result = MagicMock()
        mock_result.one.return_value = summary_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get(
                "/metrics/summary?start_date=2026-01-01&end_date=2026-01-31"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ride_count"] == 4
        assert Decimal(data["total_tss"]) == Decimal("340.5")
        assert data["total_duration_seconds"] == 14400
        assert data["start_date"] == "2026-01-01"
        assert data["end_date"] == "2026-01-31"

    @pytest.mark.asyncio
    async def test_summary_date_range_validation(self, client: AsyncClient) -> None:
        """GET /metrics/summary rejects start_date > end_date."""
        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get(
                "/metrics/summary?start_date=2026-06-01&end_date=2026-01-01"
            )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_summary_default_date_range(self, client: AsyncClient) -> None:
        """GET /metrics/summary without dates defaults to last 30 days."""
        summary_row = _make_summary_row(ride_count=0, total_tss=Decimal("0"))

        mock_result = MagicMock()
        mock_result.one.return_value = summary_row

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        mock_cache = _disable_cache()
        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get("/metrics/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["ride_count"] == 0

    @pytest.mark.asyncio
    async def test_summary_cache_hit_skips_db(self, client: AsyncClient) -> None:
        """When cache has summary data, DB is not queried."""
        cached_data = {
            "total_tss": "100",
            "ride_count": 2,
            "total_duration_seconds": 7200,
            "total_distance_meters": "100000",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }
        mock_cache = MagicMock()
        mock_cache.get_json = AsyncMock(return_value=cached_data)
        mock_cache.set_json = AsyncMock()
        mock_cache.close = AsyncMock()

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        with patch("app.routers.metrics._get_cache", return_value=mock_cache):
            response = await client.get(
                "/metrics/summary?start_date=2026-01-01&end_date=2026-01-31"
            )

        assert response.status_code == 200
        mock_db.execute.assert_not_awaited()
