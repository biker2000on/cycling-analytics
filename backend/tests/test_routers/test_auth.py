"""Tests for the authentication API endpoints (Phase 5)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user_or_default, get_db
from app.main import app as the_app
from app.security import create_access_token, create_refresh_token, hash_password


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides: object) -> SimpleNamespace:
    """Create a fake User-like object."""
    defaults: dict[str, object] = {
        "id": 1,
        "email": "rider@example.com",
        "password_hash": hash_password("securepass123"),
        "display_name": "Test Rider",
        "weight_kg": None,
        "date_of_birth": None,
        "timezone": "UTC",
        "created_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tests: POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_creates_user(self, client: AsyncClient) -> None:
        """POST /auth/register creates a new user and returns tokens."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "securepass123",
                "display_name": "New Rider",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 1800
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        """POST /auth/register with existing email returns 409."""
        existing_user = _make_user()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/register",
            json={
                "email": "rider@example.com",
                "password": "securepass123",
                "display_name": "Duplicate Rider",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_short_password_returns_422(self, client: AsyncClient) -> None:
        """POST /auth/register with password < 8 chars returns 422."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        _override_db(mock_db)

        response = await client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "short",
                "display_name": "New Rider",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for user login."""

    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, client: AsyncClient) -> None:
        """POST /auth/login with valid credentials returns tokens."""
        user = _make_user(password_hash=hash_password("securepass123"))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/login",
            json={
                "email": "rider@example.com",
                "password": "securepass123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_invalid_password_returns_401(self, client: AsyncClient) -> None:
        """POST /auth/login with wrong password returns 401."""
        user = _make_user(password_hash=hash_password("securepass123"))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/login",
            json={
                "email": "rider@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_unknown_email_returns_401(self, client: AsyncClient) -> None:
        """POST /auth/login with unknown email returns 401."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "somepassword",
            },
        )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Protected endpoint access
# ---------------------------------------------------------------------------


class TestProtectedEndpoints:
    """Tests for JWT-protected endpoint access."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token_fallback_debug(
        self, client: AsyncClient
    ) -> None:
        """In DEBUG mode, endpoints without token fallback to seed user stub."""
        # get_current_user_or_default returns _SEED_USER stub (no DB query)
        # so only endpoint DB calls happen: count + list

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
        response = await client.get("/activities")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(self, client: AsyncClient) -> None:
        """Endpoint with valid Bearer token returns data."""
        user = _make_user(id=42)
        token = create_access_token(42)

        # First call: get_current_user fetches user by id
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = user

        # Second call: count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        # Third call: list query
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[mock_user_result, mock_count_result, mock_list_result]
        )
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get(
            "/activities",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Endpoint with invalid Bearer token returns 401."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get(
            "/activities",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client: AsyncClient) -> None:
        """Endpoint with expired token returns 401."""
        # Create a token that expired 1 hour ago
        token = create_access_token(1, expires_delta=timedelta(seconds=-3600))

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get(
            "/activities",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests: POST /auth/refresh
# ---------------------------------------------------------------------------


class TestRefreshToken:
    """Tests for token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token_works(self, client: AsyncClient) -> None:
        """POST /auth/refresh with valid refresh token returns new tokens."""
        user = _make_user(id=5)
        refresh_token = create_refresh_token(5)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_returns_401(self, client: AsyncClient) -> None:
        """POST /auth/refresh with an access token (wrong type) returns 401."""
        access_token = create_access_token(1)

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401
        assert "token type" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refresh_with_expired_token_returns_401(self, client: AsyncClient) -> None:
        """POST /auth/refresh with expired refresh token returns 401."""
        token = create_refresh_token(1, expires_delta=timedelta(seconds=-3600))

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": token},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
