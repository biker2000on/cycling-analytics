"""Tests for the user settings API endpoints -- Plan 4.5."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: object) -> SimpleNamespace:
    """Create a fake UserSettings-like object with Phase 4.5 fields."""
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "ftp_watts": Decimal("280"),
        "ftp_method": "manual",
        "ftp_updated_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        "preferred_threshold_method": "manual",
        "calendar_start_day": 1,
        "weight_kg": Decimal("75.0"),
        "date_of_birth": None,
        "unit_system": "metric",
        "theme": "light",
        "hr_zones": None,
        "created_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tests: GET /settings
# ---------------------------------------------------------------------------


class TestGetSettings:
    """Tests for the full user settings endpoint."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_preferences(self, client: AsyncClient) -> None:
        """GET /settings returns full user preferences."""
        settings = _make_settings()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = settings

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["ftp_watts"]) == Decimal("280")
        assert data["ftp_method"] == "manual"
        assert data["preferred_threshold_method"] == "manual"
        assert data["calendar_start_day"] == 1
        assert Decimal(data["weight_kg"]) == Decimal("75.0")

    @pytest.mark.asyncio
    async def test_get_settings_no_record_returns_defaults(self, client: AsyncClient) -> None:
        """GET /settings returns defaults when no settings record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["ftp_watts"] is None
        assert data["preferred_threshold_method"] == "manual"
        assert data["calendar_start_day"] == 1

    @pytest.mark.asyncio
    async def test_get_settings_with_all_fields(self, client: AsyncClient) -> None:
        """GET /settings returns all fields including date_of_birth."""
        settings = _make_settings(date_of_birth="1990-06-15")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = settings

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1990-06-15"


# ---------------------------------------------------------------------------
# Tests: PUT /settings
# ---------------------------------------------------------------------------


class TestUpdateSettings:
    """Tests for updating user preferences."""

    @pytest.mark.asyncio
    async def test_put_updates_preferred_method(self, client: AsyncClient) -> None:
        """PUT /settings updates preferred_threshold_method."""
        existing = _make_settings()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"preferred_threshold_method": "pct_20min"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_threshold_method"] == "pct_20min"

    @pytest.mark.asyncio
    async def test_put_updates_multiple_fields(self, client: AsyncClient) -> None:
        """PUT /settings can update multiple fields at once."""
        existing = _make_settings()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={
                "preferred_threshold_method": "pct_8min",
                "calendar_start_day": 7,
                "weight_kg": 72.5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_threshold_method"] == "pct_8min"
        assert data["calendar_start_day"] == 7
        assert Decimal(data["weight_kg"]) == Decimal("72.5")

    @pytest.mark.asyncio
    async def test_put_creates_settings_if_none_exist(self, client: AsyncClient) -> None:
        """PUT /settings creates a new settings record if none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"preferred_threshold_method": "pct_20min"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_threshold_method"] == "pct_20min"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_invalid_method_returns_400(self, client: AsyncClient) -> None:
        """PUT /settings with invalid threshold method returns 400."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"preferred_threshold_method": "invalid_method"},
        )

        assert response.status_code == 400
        assert "Invalid threshold method" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_put_partial_update_preserves_other_fields(self, client: AsyncClient) -> None:
        """PUT /settings with partial data preserves unset fields."""
        existing = _make_settings(
            preferred_threshold_method="manual",
            calendar_start_day=1,
            weight_kg=Decimal("75.0"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        # Only update calendar_start_day
        response = await client.put(
            "/settings",
            json={"calendar_start_day": 7},
        )

        assert response.status_code == 200
        data = response.json()
        # Calendar day updated
        assert data["calendar_start_day"] == 7
        # Other fields preserved
        assert data["preferred_threshold_method"] == "manual"
        assert Decimal(data["weight_kg"]) == Decimal("75.0")

    @pytest.mark.asyncio
    async def test_put_calendar_day_validation(self, client: AsyncClient) -> None:
        """PUT /settings rejects calendar_start_day outside 1-7."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"calendar_start_day": 8},
        )

        assert response.status_code == 422  # Pydantic validation

    @pytest.mark.asyncio
    async def test_get_settings_includes_unit_system(self, client: AsyncClient) -> None:
        """GET /settings returns unit_system field with default metric."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["unit_system"] == "metric"

    @pytest.mark.asyncio
    async def test_put_unit_system_imperial(self, client: AsyncClient) -> None:
        """PUT /settings with unit_system=imperial persists the value."""
        existing = _make_settings()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"unit_system": "imperial"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["unit_system"] == "imperial"

    @pytest.mark.asyncio
    async def test_put_invalid_unit_system_returns_400(self, client: AsyncClient) -> None:
        """PUT /settings with invalid unit_system returns 400."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"unit_system": "banana"},
        )

        assert response.status_code == 400
        assert "Invalid unit system" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_settings_includes_theme(self, client: AsyncClient) -> None:
        """GET /settings returns theme field with default light."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "light"

    @pytest.mark.asyncio
    async def test_put_theme_dark(self, client: AsyncClient) -> None:
        """PUT /settings with theme=dark persists the value."""
        existing = _make_settings()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"theme": "dark"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_put_theme_system(self, client: AsyncClient) -> None:
        """PUT /settings with theme=system persists the value."""
        existing = _make_settings()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"theme": "system"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "system"

    @pytest.mark.asyncio
    async def test_put_invalid_theme_returns_400(self, client: AsyncClient) -> None:
        """PUT /settings with invalid theme returns 400."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put(
            "/settings",
            json={"theme": "rainbow"},
        )

        assert response.status_code == 400
        assert "Invalid theme" in response.json()["detail"]
