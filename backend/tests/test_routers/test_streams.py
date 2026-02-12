"""Tests for the activity streams API endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.schemas.stream import StreamResponse, StreamStats, StreamSummaryResponse


def _make_stream_response(activity_id: int = 1, count: int = 5) -> StreamResponse:
    """Build a synthetic StreamResponse for testing."""
    base_ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
    return StreamResponse(
        activity_id=activity_id,
        point_count=count,
        stats=StreamStats(
            power_avg=Decimal("200"),
            power_max=300,
            hr_avg=Decimal("150"),
            hr_max=175,
            speed_avg=Decimal("8.5"),
            speed_max=Decimal("12.1"),
            altitude_min=Decimal("100"),
            altitude_max=Decimal("250"),
        ),
        timestamps=[
            datetime(2026, 1, 15, 10, 0, i, tzinfo=UTC) for i in range(count)
        ],
        power=[200 + i for i in range(count)],
        heart_rate=[150 + i for i in range(count)],
        cadence=[90 + i for i in range(count)],
        speed_mps=[Decimal("8.5") for _ in range(count)],
        altitude_meters=[Decimal(str(100 + i * 10)) for i in range(count)],
        distance_meters=[Decimal(str(i * 100)) for i in range(count)],
        temperature_c=[Decimal("22") for _ in range(count)],
        latitude=[Decimal("40.7128") for _ in range(count)],
        longitude=[Decimal("-74.0060") for _ in range(count)],
        grade_percent=[Decimal("2.5") for _ in range(count)],
    )


def _make_summary_response(
    activity_id: int = 1, count: int = 3, original: int = 10
) -> StreamSummaryResponse:
    """Build a synthetic StreamSummaryResponse for testing."""
    return StreamSummaryResponse(
        activity_id=activity_id,
        point_count=count,
        original_point_count=original,
        stats=StreamStats(
            power_avg=Decimal("200"),
            power_max=300,
        ),
        timestamps=[
            datetime(2026, 1, 15, 10, 0, i, tzinfo=UTC) for i in range(count)
        ],
        power=[200 + i for i in range(count)],
        heart_rate=[150 + i for i in range(count)],
        cadence=[90 + i for i in range(count)],
        speed_mps=[Decimal("8.5") for _ in range(count)],
        altitude_meters=[Decimal(str(100 + i * 10)) for i in range(count)],
    )


def _mock_activity(activity_id: int = 1) -> MagicMock:
    """Create a mock Activity ORM object."""
    activity = MagicMock()
    activity.id = activity_id
    activity.user_id = 1
    activity.name = "Morning Ride"
    activity.sport_type = "cycling"
    return activity


def _mock_db_with_activity(activity: MagicMock | None) -> AsyncMock:
    """Create a mock AsyncSession that returns the given activity on execute."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = activity
    db.execute.return_value = result_mock
    return db


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    return create_app()


class TestGetStreams:
    """Tests for GET /activities/{id}/streams."""

    @pytest.mark.asyncio
    async def test_returns_columnar_data(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns stream data in columnar format for an existing activity."""
        mock_activity = _mock_activity(1)
        stream_resp = _make_stream_response(1, 5)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        app.dependency_overrides[
            __import__("app.dependencies", fromlist=["get_db"]).get_db
        ] = override_get_db

        with patch(
            "app.routers.streams.get_activity_streams",
            return_value=stream_resp,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/activities/1/streams")

            assert resp.status_code == 200
            data = resp.json()
            assert data["activity_id"] == 1
            assert data["point_count"] == 5
            assert len(data["timestamps"]) == 5
            assert len(data["power"]) == 5
            assert len(data["heart_rate"]) == 5
            assert "stats" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_nonexistent_activity_returns_404(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns 404 for a non-existent activity."""

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(None)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/activities/99999/streams")

        assert resp.status_code == 404

        app.dependency_overrides.clear()


class TestGetStreamsSummary:
    """Tests for GET /activities/{id}/streams/summary."""

    @pytest.mark.asyncio
    async def test_returns_downsampled_data(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns downsampled stream data with correct point count."""
        mock_activity = _mock_activity(1)
        summary_resp = _make_summary_response(1, count=3, original=10)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch(
            "app.routers.streams.get_activity_streams_summary",
            return_value=summary_resp,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/activities/1/streams/summary?points=3")

            assert resp.status_code == 200
            data = resp.json()
            assert data["point_count"] == 3
            assert data["original_point_count"] == 10
            assert len(data["timestamps"]) == 3

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_preserves_count_constraint(self, app) -> None:  # type: ignore[no-untyped-def]
        """The returned point_count does not exceed the requested points."""
        mock_activity = _mock_activity(1)
        summary_resp = _make_summary_response(1, count=50, original=1000)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch(
            "app.routers.streams.get_activity_streams_summary",
            return_value=summary_resp,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/activities/1/streams/summary?points=50")

            assert resp.status_code == 200
            data = resp.json()
            assert data["point_count"] <= 50

        app.dependency_overrides.clear()
