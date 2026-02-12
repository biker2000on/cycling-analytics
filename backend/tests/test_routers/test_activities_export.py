"""Tests for activity export endpoints — FIT file download and CSV export."""

import csv
import io
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


def _mock_activity(
    activity_id: int = 1,
    fit_file_path: str | None = "1/2026/01/abc123.fit",
    source_value: str = "fit_upload",
) -> MagicMock:
    """Create a mock Activity ORM object."""
    activity = MagicMock()
    activity.id = activity_id
    activity.user_id = 1
    activity.name = "Morning Ride"
    activity.sport_type = "cycling"
    activity.fit_file_path = fit_file_path
    activity.activity_date = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
    activity.duration_seconds = 3600
    activity.distance_meters = Decimal("25000")
    activity.avg_power_watts = Decimal("200")
    activity.max_power_watts = Decimal("350")
    activity.avg_hr = 150
    activity.max_hr = 175
    activity.tss = Decimal("75")
    activity.np_watts = Decimal("220")
    activity.intensity_factor = Decimal("0.88")
    activity.source = MagicMock()
    activity.source.value = source_value
    return activity


def _mock_db_with_activity(activity: MagicMock | None) -> AsyncMock:
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = activity
    db.execute.return_value = result_mock
    return db


def _mock_db_with_activities(activities: list[MagicMock]) -> AsyncMock:
    """Create a mock db that returns a list of activities for scalars().all()."""
    db = AsyncMock()
    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = activities
    result_mock.scalars.return_value = scalars_mock
    db.execute.return_value = result_mock
    return db


@pytest.fixture
def app():  # type: ignore[no-untyped-def]
    return create_app()


class TestDownloadFitFile:
    """Tests for GET /activities/{id}/fit-file."""

    @pytest.mark.asyncio
    async def test_download_fit_file(self, app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
        """Returns the FIT file as binary download with correct headers."""
        # Create a temporary FIT-like file
        fit_content = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT" + b"\x00" * 100
        fit_dir = tmp_path / "1" / "2026" / "01"
        fit_dir.mkdir(parents=True)
        fit_file = fit_dir / "abc123.fit"
        fit_file.write_bytes(fit_content)

        mock_activity = _mock_activity(1, fit_file_path="1/2026/01/abc123.fit")

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        with patch("app.routers.activities.get_settings") as mock_settings:
            settings = MagicMock()
            settings.FIT_STORAGE_PATH = str(tmp_path)
            mock_settings.return_value = settings

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/activities/1/fit-file")

            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/octet-stream"
            assert "activity_1.fit" in resp.headers.get("content-disposition", "")
            assert resp.content == fit_content

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_manual_activity_returns_404(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns 404 for an activity without a FIT file (manual entry)."""
        mock_activity = _mock_activity(1, fit_file_path=None, source_value="manual")

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(mock_activity)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/activities/1/fit-file")

        assert resp.status_code == 404
        assert "no FIT file" in resp.json()["detail"].lower() or "manual" in resp.json()["detail"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_nonexistent_activity_returns_404(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns 404 when the activity does not exist."""

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activity(None)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/activities/99999/fit-file")

        assert resp.status_code == 404

        app.dependency_overrides.clear()


class TestExportCsv:
    """Tests for GET /activities/export-csv."""

    @pytest.mark.asyncio
    async def test_returns_valid_csv(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns a valid CSV with the expected columns and data."""
        activities = [_mock_activity(i) for i in range(3)]

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activities(activities)

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/activities/export-csv")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "activities.csv" in resp.headers.get("content-disposition", "")

        # Parse the CSV content
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        header = rows[0]

        assert "date" in header
        assert "name" in header
        assert "sport_type" in header
        assert "duration_seconds" in header
        assert "distance_meters" in header
        assert "source" in header

        # 3 data rows + 1 header
        assert len(rows) == 4

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_empty_export_csv(self, app) -> None:  # type: ignore[no-untyped-def]
        """Returns CSV with only header when no activities exist."""

        async def override_get_db():  # type: ignore[no-untyped-def]
            yield _mock_db_with_activities([])

        from app.dependencies import get_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/activities/export-csv")

        assert resp.status_code == 200

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        # Header only
        assert len(rows) == 1

        app.dependency_overrides.clear()
