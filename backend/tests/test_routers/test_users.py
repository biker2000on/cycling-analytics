"""Tests for user profile endpoints (Phase 5)."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_or_default, get_db
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


def _override_current_user(user: SimpleNamespace) -> None:
    """Override get_current_user_or_default to return a specific user."""

    async def _fake_user():  # type: ignore[no-untyped-def]
        return user

    the_app.dependency_overrides[get_current_user_or_default] = _fake_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides: object) -> SimpleNamespace:
    """Create a fake User-like object."""
    defaults: dict[str, object] = {
        "id": 1,
        "email": "rider@example.com",
        "password_hash": "$2b$12$fake",
        "display_name": "Test Rider",
        "weight_kg": Decimal("75.0"),
        "date_of_birth": None,
        "timezone": "UTC",
        "created_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tests: GET /users/me
# ---------------------------------------------------------------------------


class TestGetProfile:
    """Tests for retrieving the current user's profile."""

    @pytest.mark.asyncio
    async def test_get_profile_returns_user(self, client: AsyncClient) -> None:
        """GET /users/me returns the current user's profile."""
        user = _make_user()
        _override_current_user(user)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        response = await client.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["email"] == "rider@example.com"
        assert data["display_name"] == "Test Rider"
        assert Decimal(data["weight_kg"]) == Decimal("75.0")
        assert data["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_get_profile_without_weight(self, client: AsyncClient) -> None:
        """GET /users/me works when weight_kg is None."""
        user = _make_user(weight_kg=None)
        _override_current_user(user)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        response = await client.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["weight_kg"] is None


# ---------------------------------------------------------------------------
# Tests: PUT /users/me
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    """Tests for updating the current user's profile."""

    @pytest.mark.asyncio
    async def test_put_updates_display_name(self, client: AsyncClient) -> None:
        """PUT /users/me updates display_name."""
        user = _make_user()
        _override_current_user(user)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        response = await client.put(
            "/users/me",
            json={"display_name": "Updated Rider"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Rider"

    @pytest.mark.asyncio
    async def test_put_updates_weight(self, client: AsyncClient) -> None:
        """PUT /users/me updates weight_kg."""
        user = _make_user()
        _override_current_user(user)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        response = await client.put(
            "/users/me",
            json={"weight_kg": 72.5},
        )

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["weight_kg"]) == Decimal("72.5")

    @pytest.mark.asyncio
    async def test_put_updates_timezone(self, client: AsyncClient) -> None:
        """PUT /users/me updates timezone."""
        user = _make_user()
        _override_current_user(user)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        response = await client.put(
            "/users/me",
            json={"timezone": "America/New_York"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_put_partial_update_preserves_other_fields(
        self, client: AsyncClient
    ) -> None:
        """PUT /users/me with partial data preserves unset fields."""
        user = _make_user(
            display_name="Original",
            weight_kg=Decimal("75.0"),
            timezone="UTC",
        )
        _override_current_user(user)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        # Only update timezone
        response = await client.put(
            "/users/me",
            json={"timezone": "Europe/London"},
        )

        assert response.status_code == 200
        data = response.json()
        # Timezone updated
        assert data["timezone"] == "Europe/London"
        # Other fields preserved
        assert data["display_name"] == "Original"
        assert Decimal(data["weight_kg"]) == Decimal("75.0")
