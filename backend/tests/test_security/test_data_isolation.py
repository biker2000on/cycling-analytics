"""Tests for data isolation between users (Phase 5).

Ensures that user A cannot access user B's activities, metrics, etc.
"""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_or_default, get_db
from app.main import app as the_app
from app.models.activity import ActivitySource, ProcessingStatus
from app.security import create_access_token


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


def _override_current_user(user: SimpleNamespace) -> None:
    """Override get_current_user_or_default to return a specific user."""

    async def _fake_user():  # type: ignore[no-untyped-def]
        return user

    the_app.dependency_overrides[get_current_user_or_default] = _fake_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: int = 1, email: str = "a@test.com") -> SimpleNamespace:
    """Create a fake User-like object."""
    return SimpleNamespace(
        id=user_id,
        email=email,
        password_hash="$2b$12$fake",
        display_name=f"User {user_id}",
        weight_kg=None,
        date_of_birth=None,
        timezone="UTC",
        created_at=datetime(2026, 2, 12, tzinfo=UTC),
        updated_at=datetime(2026, 2, 12, tzinfo=UTC),
    )


def _make_activity(activity_id: int, user_id: int) -> SimpleNamespace:
    """Create a fake Activity-like object."""
    return SimpleNamespace(
        id=activity_id,
        user_id=user_id,
        external_id=None,
        source=ActivitySource.fit_upload,
        activity_date=datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
        name=f"Activity {activity_id}",
        sport_type="cycling",
        duration_seconds=3600,
        distance_meters=Decimal("50000"),
        elevation_gain_meters=Decimal("500"),
        avg_power_watts=Decimal("200"),
        max_power_watts=Decimal("400"),
        avg_hr=145,
        max_hr=175,
        avg_cadence=90,
        calories=800,
        tss=None,
        np_watts=None,
        intensity_factor=None,
        fit_file_path=None,
        device_name=None,
        notes=None,
        processing_status=ProcessingStatus.complete,
        error_message=None,
        file_hash=f"hash{activity_id}",
        created_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Tests: Cross-user activity isolation
# ---------------------------------------------------------------------------


class TestActivityIsolation:
    """Verify user A cannot access user B's activities."""

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_activity(self, client: AsyncClient) -> None:
        """GET /activities/{id} returns 404 for another user's activity."""
        user_a = _make_user(user_id=10, email="a@test.com")
        _override_current_user(user_a)

        # Activity belongs to user 20, not user 10
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not found for user 10

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/activities/999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_user_only_sees_own_activities(self, client: AsyncClient) -> None:
        """GET /activities returns only the current user's activities."""
        user_a = _make_user(user_id=10, email="a@test.com")
        _override_current_user(user_a)

        activity_a = _make_activity(activity_id=1, user_id=10)

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [activity_a]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_list_result]
        )
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/activities")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_user_a_cannot_delete_user_b_activity(self, client: AsyncClient) -> None:
        """DELETE /activities/{id} returns 404 for another user's activity."""
        user_a = _make_user(user_id=10, email="a@test.com")
        _override_current_user(user_a)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.delete("/activities/999")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Cross-user metrics isolation
# ---------------------------------------------------------------------------


class TestMetricsIsolation:
    """Verify user A cannot access user B's metrics."""

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_metrics(self, client: AsyncClient) -> None:
        """GET /metrics/activities/{id} returns 404 for another user's activity metrics."""
        user_a = _make_user(user_id=10, email="a@test.com")
        _override_current_user(user_a)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)

        with patch("app.routers.metrics._get_cache") as mock_cache_fn:
            mock_cache = AsyncMock()
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.close = AsyncMock()
            mock_cache_fn.return_value = mock_cache

            response = await client.get("/metrics/activities/999")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Invalid auth header
# ---------------------------------------------------------------------------


class TestInvalidAuth:
    """Verify invalid auth headers are rejected."""

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self, client: AsyncClient) -> None:
        """Providing an invalid Bearer token returns 401."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get(
            "/activities",
            headers={"Authorization": "Bearer bad.token.value"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_auth_header_falls_back_in_debug(
        self, client: AsyncClient
    ) -> None:
        """Malformed Authorization header (not Bearer) falls back to seed user in DEBUG."""
        # In DEBUG mode without "Bearer " prefix, get_current_user_or_default
        # falls back to seed user stub — only Bearer tokens are validated
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_list_result]
        )
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get(
            "/activities",
            headers={"Authorization": "NotBearer sometoken"},
        )

        assert response.status_code == 200
