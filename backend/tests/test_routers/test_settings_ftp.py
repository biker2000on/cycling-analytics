"""Tests for the FTP settings API endpoints — Plan 2.2."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_db
from app.main import app as the_app


def _make_fake_settings(**overrides: object) -> SimpleNamespace:
    """Create a fake UserSettings-like object."""
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "ftp_watts": Decimal("280"),
        "ftp_method": "manual",
        "ftp_updated_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        "hr_zones": None,
        "weight_kg": None,
        "created_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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


# -----------------------------------------------------------------------
# POST /settings/ftp
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_ftp_creates_setting(client: AsyncClient) -> None:
    """POST /settings/ftp should create a new FTP setting when none exists."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # no existing setting

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.post("/settings/ftp", json={"ftp_watts": 280})

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["ftp_watts"]) == Decimal("280")
    assert data["ftp_method"] == "manual"
    assert data["updated_at"] is not None
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_post_ftp_updates_existing(client: AsyncClient) -> None:
    """POST /settings/ftp should update existing FTP setting."""
    existing = _make_fake_settings(ftp_watts=Decimal("250"))

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.post("/settings/ftp", json={"ftp_watts": 290})

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["ftp_watts"]) == Decimal("290")


@pytest.mark.asyncio
async def test_post_ftp_invalid_value(client: AsyncClient) -> None:
    """POST /settings/ftp with invalid value should return 422."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    _override_db(mock_db)

    response = await client.post("/settings/ftp", json={"ftp_watts": -10})
    assert response.status_code == 422


# -----------------------------------------------------------------------
# GET /settings/ftp
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ftp_returns_value(client: AsyncClient) -> None:
    """GET /settings/ftp should return current FTP when configured."""
    existing = _make_fake_settings()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.get("/settings/ftp")

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["ftp_watts"]) == Decimal("280")
    assert data["ftp_method"] == "manual"


@pytest.mark.asyncio
async def test_get_ftp_not_configured_returns_404(client: AsyncClient) -> None:
    """GET /settings/ftp should return 404 when no FTP is set."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.get("/settings/ftp")

    assert response.status_code == 404
    assert "not configured" in response.json()["detail"].lower()
