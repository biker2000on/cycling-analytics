"""Tests for the thresholds API endpoints -- Plan 4.1."""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_threshold(
    threshold_id: int = 1,
    method: str = "manual",
    ftp_watts: Decimal = Decimal("275"),
    effective_date: date = date(2026, 1, 1),
    source_activity_id: int | None = None,
    is_active: bool = True,
    notes: str | None = None,
) -> SimpleNamespace:
    """Create a fake Threshold-like object."""
    return SimpleNamespace(
        id=threshold_id,
        user_id=1,
        method=method,
        ftp_watts=ftp_watts,
        effective_date=effective_date,
        source_activity_id=source_activity_id,
        is_active=is_active,
        notes=notes,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Tests: POST /thresholds
# ---------------------------------------------------------------------------


class TestCreateThreshold:
    """Tests for creating threshold entries."""

    @pytest.mark.asyncio
    async def test_post_creates_threshold(self, client: AsyncClient) -> None:
        """POST /thresholds creates a new threshold entry."""
        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # Check for existing -- none
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=fake_execute)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/thresholds",
            json={
                "method": "manual",
                "ftp_watts": 275,
                "effective_date": "2026-01-01",
                "notes": "Test threshold",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert Decimal(data["ftp_watts"]) == Decimal("275")
        assert data["method"] == "manual"
        assert data["effective_date"] == "2026-01-01"
        assert data["is_active"] is True
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_conflict_returns_409(self, client: AsyncClient) -> None:
        """POST /thresholds with duplicate method+date returns 409."""
        existing = _make_threshold()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.post(
            "/thresholds",
            json={
                "method": "manual",
                "ftp_watts": 280,
                "effective_date": "2026-01-01",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: GET /thresholds
# ---------------------------------------------------------------------------


class TestGetThresholds:
    """Tests for listing threshold history."""

    @pytest.mark.asyncio
    async def test_get_returns_history(self, client: AsyncClient) -> None:
        """GET /thresholds returns all thresholds sorted by date."""
        rows = [
            _make_threshold(threshold_id=2, effective_date=date(2026, 2, 1), ftp_watts=Decimal("280")),
            _make_threshold(threshold_id=1, effective_date=date(2026, 1, 1), ftp_watts=Decimal("275")),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/thresholds")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 2
        assert Decimal(data["thresholds"][0]["ftp_watts"]) == Decimal("280")
        assert Decimal(data["thresholds"][1]["ftp_watts"]) == Decimal("275")

    @pytest.mark.asyncio
    async def test_get_filtered_by_method(self, client: AsyncClient) -> None:
        """GET /thresholds?method=pct_20min filters by method."""
        rows = [
            _make_threshold(method="pct_20min", ftp_watts=Decimal("290")),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/thresholds?method=pct_20min")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 1
        assert data["thresholds"][0]["method"] == "pct_20min"

    @pytest.mark.asyncio
    async def test_get_empty_history(self, client: AsyncClient) -> None:
        """GET /thresholds with no thresholds returns empty list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/thresholds")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 0


# ---------------------------------------------------------------------------
# Tests: GET /thresholds/current
# ---------------------------------------------------------------------------


class TestGetCurrentThreshold:
    """Tests for getting the current active threshold."""

    @pytest.mark.asyncio
    async def test_get_current_returns_most_recent(self, client: AsyncClient) -> None:
        """GET /thresholds/current returns the most recent active threshold."""
        threshold = _make_threshold(ftp_watts=Decimal("285"))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = threshold

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/thresholds/current?method=manual")

        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["ftp_watts"]) == Decimal("285")
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_current_not_found_returns_404(self, client: AsyncClient) -> None:
        """GET /thresholds/current returns 404 when no active threshold."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.get("/thresholds/current?method=pct_20min")

        assert response.status_code == 404
        assert "No active threshold" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: PUT /thresholds/{id}/activate
# ---------------------------------------------------------------------------


class TestActivateThreshold:
    """Tests for activating a threshold entry."""

    @pytest.mark.asyncio
    async def test_activate_sets_active_flag(self, client: AsyncClient) -> None:
        """PUT /thresholds/{id}/activate should set is_active=True."""
        threshold = _make_threshold(threshold_id=5, is_active=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = threshold

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put("/thresholds/5/activate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_activate_not_found_returns_404(self, client: AsyncClient) -> None:
        """PUT /thresholds/{id}/activate returns 404 for unknown threshold."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        _override_db(mock_db)
        response = await client.put("/thresholds/999/activate")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
