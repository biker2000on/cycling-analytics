"""Tests for the activities API endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_db
from app.main import app as the_app
from app.models.activity import ActivitySource, ProcessingStatus


def _make_valid_fit_bytes() -> bytes:
    """Create minimal bytes that pass FIT magic validation.

    FIT files have ".FIT" at byte offset 8-11.
    """
    header = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT"
    return header + b"\x00" * 100


def _make_fake_activity(**overrides: object) -> SimpleNamespace:
    """Create a fake Activity-like object with attribute access for model_validate."""
    defaults: dict[str, object] = {
        "id": 1,
        "user_id": 1,
        "external_id": None,
        "source": ActivitySource.fit_upload,
        "activity_date": datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
        "name": "Test Ride",
        "sport_type": "cycling",
        "duration_seconds": 3600,
        "distance_meters": Decimal("50000"),
        "elevation_gain_meters": Decimal("500"),
        "avg_power_watts": Decimal("200"),
        "max_power_watts": Decimal("400"),
        "avg_hr": 145,
        "max_hr": 175,
        "avg_cadence": 90,
        "calories": 800,
        "tss": None,
        "np_watts": None,
        "intensity_factor": None,
        "fit_file_path": "1/2026/02/test.fit",
        "device_name": "garmin edge_530",
        "notes": None,
        "processing_status": ProcessingStatus.pending,
        "error_message": None,
        "file_hash": "abc123",
        "created_at": datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 2, 10, 12, 0, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    """Async HTTP test client using the global app instance (supports dependency overrides)."""
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
# POST /activities/upload-fit
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_valid_fit_returns_202(client: AsyncClient) -> None:
    """Upload a valid FIT file should return 202 with activity_id and task_id."""
    fake_activity = _make_fake_activity(id=42)
    fake_task_id = "celery-task-uuid-123"

    with (
        patch("app.routers.activities.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.return_value = (fake_activity, fake_task_id)
        fit_content = _make_valid_fit_bytes()
        response = await client.post(
            "/activities/upload-fit",
            files={"file": ("ride.fit", BytesIO(fit_content), "application/octet-stream")},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["activity_id"] == 42
    assert data["task_id"] == "celery-task-uuid-123"


@pytest.mark.asyncio
async def test_upload_oversized_file_returns_413(client: AsyncClient) -> None:
    """Upload a file exceeding 50 MB should return 413."""
    header = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT"
    oversized = header + b"\x00" * (50 * 1024 * 1024 + 1)

    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post(
            "/activities/upload-fit",
            files={"file": ("big.fit", BytesIO(oversized), "application/octet-stream")},
        )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_non_fit_returns_400(client: AsyncClient) -> None:
    """Upload a file without FIT magic bytes should return 400."""
    not_fit = b"this is not a FIT file at all, just random bytes"

    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post(
            "/activities/upload-fit",
            files={"file": ("bad.bin", BytesIO(not_fit), "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rate_limit_returns_429(client: AsyncClient) -> None:
    """Exceeding rate limit should return 429."""
    with patch("app.routers.activities._check_rate_limit", return_value=False):
        fit_content = _make_valid_fit_bytes()
        response = await client.post(
            "/activities/upload-fit",
            files={"file": ("ride.fit", BytesIO(fit_content), "application/octet-stream")},
        )

    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_duplicate_returns_409(client: AsyncClient) -> None:
    """Upload a duplicate file should return 409."""
    from app.services.import_service import DuplicateFileError

    with (
        patch("app.routers.activities.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = DuplicateFileError(existing_activity_id=99)
        fit_content = _make_valid_fit_bytes()
        response = await client.post(
            "/activities/upload-fit",
            files={"file": ("ride.fit", BytesIO(fit_content), "application/octet-stream")},
        )

    assert response.status_code == 409
    assert "Duplicate" in response.json()["detail"]


# -----------------------------------------------------------------------
# GET /activities
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_activities_returns_paginated(client: AsyncClient) -> None:
    """GET /activities should return paginated list."""
    fake_activity = _make_fake_activity()

    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    mock_list_result = MagicMock()
    mock_list_result.scalars.return_value.all.return_value = [fake_activity]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.get("/activities?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] == 1
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Test Ride"


# -----------------------------------------------------------------------
# GET /activities/{id}
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_activity_returns_detail(client: AsyncClient) -> None:
    """GET /activities/{id} should return activity detail."""
    fake_activity = _make_fake_activity(id=7)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_activity

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.get("/activities/7")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 7
    assert data["name"] == "Test Ride"


@pytest.mark.asyncio
async def test_get_activity_not_found_returns_404(client: AsyncClient) -> None:
    """GET /activities/{id} for missing activity should return 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.get("/activities/999")

    assert response.status_code == 404


# -----------------------------------------------------------------------
# DELETE /activities/{id}
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_activity_returns_204(client: AsyncClient) -> None:
    """DELETE /activities/{id} should return 204 and remove the activity."""
    fake_activity = _make_fake_activity(id=10, fit_file_path="1/2026/02/test.fit")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_activity

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    with patch("app.routers.activities.delete_fit_file") as mock_del_file:
        response = await client.delete("/activities/10")
        mock_del_file.assert_called_once_with("1/2026/02/test.fit")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_activity_not_found_returns_404(client: AsyncClient) -> None:
    """DELETE /activities/{id} for missing activity should return 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.delete("/activities/999")

    assert response.status_code == 404


# -----------------------------------------------------------------------
# POST /activities/{id}/reprocess
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reprocess_activity_success(client: AsyncClient) -> None:
    """POST /activities/{id}/reprocess should reset status, clear streams/laps, and return 202."""
    fake_activity = _make_fake_activity(
        id=15,
        fit_file_path="1/2026/02/test.fit",
        processing_status=ProcessingStatus.complete,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_activity

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    _override_db(mock_db)

    with (
        patch("app.workers.tasks.fit_import.process_fit_upload") as mock_task,
        patch("app.routers.activities.Path") as mock_path,
        patch("app.routers.activities.get_settings") as mock_settings,
    ):
        mock_settings.return_value.FIT_STORAGE_PATH = "/storage"
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value.__truediv__.return_value = mock_path_instance

        mock_task_instance = MagicMock()
        mock_task_instance.id = "task-abc-123"
        mock_task.delay.return_value = mock_task_instance

        response = await client.post("/activities/15/reprocess")

    assert response.status_code == 202
    data = response.json()
    assert data["activity_id"] == 15
    assert data["task_id"] == "task-abc-123"
    assert fake_activity.processing_status == ProcessingStatus.pending
    assert fake_activity.error_message is None


@pytest.mark.asyncio
async def test_reprocess_activity_no_fit_file(client: AsyncClient) -> None:
    """Reprocess activity without fit_file_path should return 400."""
    fake_activity = _make_fake_activity(id=20, fit_file_path=None, source=ActivitySource.manual)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_activity

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.post("/activities/20/reprocess")

    assert response.status_code == 400
    assert "no FIT file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_reprocess_activity_not_found(client: AsyncClient) -> None:
    """Reprocess non-existent activity should return 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)
    response = await client.post("/activities/999/reprocess")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reprocess_activity_file_not_on_disk(client: AsyncClient) -> None:
    """Reprocess when FIT file missing from disk should return 404."""
    fake_activity = _make_fake_activity(id=25, fit_file_path="1/2026/02/missing.fit")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_activity

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    _override_db(mock_db)

    with (
        patch("app.routers.activities.Path") as mock_path,
        patch("app.routers.activities.get_settings") as mock_settings,
    ):
        mock_settings.return_value.FIT_STORAGE_PATH = "/storage"
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value.__truediv__.return_value = mock_path_instance

        response = await client.post("/activities/25/reprocess")

    assert response.status_code == 404
    assert "not found on disk" in response.json()["detail"]
