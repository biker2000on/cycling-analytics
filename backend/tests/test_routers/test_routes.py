"""Tests for the activity route (GeoJSON) API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.schemas.route import RouteGeoJSON


def _mock_activity(activity_id: int = 1) -> MagicMock:
    activity = MagicMock()
    activity.id = activity_id
    activity.user_id = 1
    activity.name = "Morning Ride"
    activity.sport_type = "cycling"
    return activity


def _mock_db_with_activity(activity: MagicMock | None) -> AsyncMock:
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = activity
    db.execute.return_value = result_mock
    return db


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    return create_app()


class TestGetRoute:
    """Tests for GET /activities/{id}/route."""

    @pytest.mark.asyncio
    async def test_returns_geojson(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns a GeoJSON Feature with LineString geometry."""
        mock_activity = _mock_activity(1)
        route = RouteGeoJSON(
            type="Feature",
            geometry={
                "type": "LineString",
                "coordinates": [
                    [-74.006, 40.7128],
                    [-74.005, 40.7130],
                    [-74.004, 40.7132],
                ],
            },
            properties={
                "activity_id": 1,
                "name": "Morning Ride",
                "sport_type": "cycling",
            },
        )

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch(
            "app.routers.routes.get_activity_route",
            return_value=route,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/activities/1/route")

            assert resp.status_code == 200
            data = resp.json()
            assert data["type"] == "Feature"
            assert data["geometry"]["type"] == "LineString"
            assert len(data["geometry"]["coordinates"]) == 3
            assert data["properties"]["activity_id"] == 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_no_gps_returns_404(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns 404 when the activity has no GPS data."""
        mock_activity = _mock_activity(1)

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch(
            "app.routers.routes.get_activity_route",
            return_value=None,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/activities/1/route")

            assert resp.status_code == 404

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
            resp = await ac.get("/activities/99999/route")

        assert resp.status_code == 404

        app.dependency_overrides.clear()
