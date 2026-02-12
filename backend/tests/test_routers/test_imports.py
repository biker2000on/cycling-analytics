"""Tests for the imports router endpoints.

Covers: archive upload, bulk upload, directory import, and batch status.
"""

import io
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.main import create_app
from app.models.import_batch import ImportBatch, ImportBatchStatus
from app.services.batch_import_service import BatchFileResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fit_content(payload: bytes = b"\x00" * 100) -> bytes:
    """Build minimal content that passes FIT magic byte validation."""
    header = bytearray(12)
    header[0] = 12
    header[8:12] = b".FIT"
    return bytes(header) + payload


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Create an in-memory zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_batch(
    batch_id: int = 1,
    total: int = 2,
    processed: int = 0,
    failed: int = 0,
    skipped: int = 0,
    status: ImportBatchStatus = ImportBatchStatus.processing,
) -> ImportBatch:
    """Create a mock ImportBatch."""
    batch = MagicMock(spec=ImportBatch)
    batch.id = batch_id
    batch.user_id = 1
    batch.total_files = total
    batch.processed_files = processed
    batch.failed_files = failed
    batch.skipped_files = skipped
    batch.status = status
    batch.created_at = datetime.now(UTC)
    batch.updated_at = datetime.now(UTC)
    return batch


def _make_results(count: int, status: str = "pending") -> list[BatchFileResult]:
    """Create a list of BatchFileResult."""
    results = []
    for i in range(count):
        r = BatchFileResult(f"file{i}.fit")
        r.status = status
        r.activity_id = i + 1
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# POST /imports/archive
# ---------------------------------------------------------------------------


class TestUploadArchive:
    @pytest.mark.asyncio
    async def test_valid_zip_returns_202(self, client: AsyncClient) -> None:
        """Valid zip with FIT files should return 202."""
        fit_content = _make_fit_content(b"\x01" * 50)
        zip_bytes = _make_zip({"ride.fit": fit_content})

        batch = _make_batch()
        results = _make_results(1)

        with patch(
            "app.routers.imports.extract_and_queue_zip",
            new_callable=AsyncMock,
            return_value=(batch, results),
        ):
            response = await client.post(
                "/imports/archive",
                files={"file": ("export.zip", zip_bytes, "application/zip")},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["id"] == 1
        assert body["total_files"] == 2
        assert len(body["items"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_zip_returns_400(self, client: AsyncClient) -> None:
        """Invalid zip should return 400."""
        with patch(
            "app.routers.imports.extract_and_queue_zip",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid zip file"),
        ):
            response = await client.post(
                "/imports/archive",
                files={"file": ("bad.zip", b"not a zip", "application/zip")},
            )

        assert response.status_code == 400
        assert "Invalid zip" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_empty_zip_returns_400(self, client: AsyncClient) -> None:
        """Zip with no FIT files should return 400."""
        zip_bytes = _make_zip({"readme.txt": b"no fit files"})

        with patch(
            "app.routers.imports.extract_and_queue_zip",
            new_callable=AsyncMock,
            side_effect=ValueError("No .fit files found in archive"),
        ):
            response = await client.post(
                "/imports/archive",
                files={"file": ("empty.zip", zip_bytes, "application/zip")},
            )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /imports/bulk
# ---------------------------------------------------------------------------


class TestUploadBulk:
    @pytest.mark.asyncio
    async def test_multiple_files_returns_202(self, client: AsyncClient) -> None:
        """Multiple FIT files should return 202."""
        fit1 = _make_fit_content(b"\x10" * 50)
        fit2 = _make_fit_content(b"\x11" * 50)

        batch = _make_batch(total=2)
        results = _make_results(2)

        with patch(
            "app.routers.imports.queue_multiple_files",
            new_callable=AsyncMock,
            return_value=(batch, results),
        ):
            response = await client.post(
                "/imports/bulk",
                files=[
                    ("files", ("ride1.fit", fit1, "application/octet-stream")),
                    ("files", ("ride2.fit", fit2, "application/octet-stream")),
                ],
            )

        assert response.status_code == 202
        body = response.json()
        assert body["total_files"] == 2
        assert len(body["items"]) == 2

    @pytest.mark.asyncio
    async def test_no_files_returns_400(self, client: AsyncClient) -> None:
        """Empty file list should return 400."""
        # Send POST with no files field at all - FastAPI will reject with 422
        response = await client.post("/imports/bulk")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /imports/directory
# ---------------------------------------------------------------------------


class TestImportDirectory:
    @pytest.mark.asyncio
    async def test_valid_directory_returns_202(self, client: AsyncClient) -> None:
        """Valid directory path should return 202."""
        batch = _make_batch(total=3)
        results = _make_results(3)

        with patch(
            "app.routers.imports.scan_directory",
            new_callable=AsyncMock,
            return_value=(batch, results),
        ):
            response = await client.post(
                "/imports/directory",
                json={"path": "/data/garmin/export"},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["total_files"] == 3

    @pytest.mark.asyncio
    async def test_path_traversal_returns_400(self, client: AsyncClient) -> None:
        """Path traversal attempt should return 400."""
        with patch(
            "app.routers.imports.scan_directory",
            new_callable=AsyncMock,
            side_effect=ValueError("Path contains invalid characters or traversal sequences"),
        ):
            response = await client.post(
                "/imports/directory",
                json={"path": "/data/../../etc/passwd"},
            )

        assert response.status_code == 400
        assert "traversal" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_nonexistent_path_returns_400(self, client: AsyncClient) -> None:
        """Nonexistent path should return 400."""
        with patch(
            "app.routers.imports.scan_directory",
            new_callable=AsyncMock,
            side_effect=ValueError("Path does not exist: /fake/path"),
        ):
            response = await client.post(
                "/imports/directory",
                json={"path": "/fake/path"},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_path_returns_422(self, client: AsyncClient) -> None:
        """Missing path field should return 422 validation error."""
        response = await client.post(
            "/imports/directory",
            json={},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /imports/{batch_id}/status
# ---------------------------------------------------------------------------


class TestGetBatchStatus:
    @pytest.mark.asyncio
    async def test_existing_batch_returns_200(self) -> None:
        """Existing batch should return 200 with status details."""
        batch = _make_batch(batch_id=42, total=3, processed=2, failed=1)

        mock_batch_result = MagicMock()
        mock_batch_result.scalar_one_or_none.return_value = batch

        mock_activities_result = MagicMock()
        mock_activities_result.scalars.return_value.all.return_value = []

        call_count = 0

        async def mock_execute(stmt: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_batch_result
            return mock_activities_result

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        async def override_get_db() -> AsyncIterator[AsyncMock]:
            yield mock_db

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/imports/42/status")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 42
        assert body["total_files"] == 3
        assert body["processed_files"] == 2
        assert body["failed_files"] == 1

    @pytest.mark.asyncio
    async def test_nonexistent_batch_returns_404(self) -> None:
        """Nonexistent batch should return 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        async def override_get_db() -> AsyncIterator[AsyncMock]:
            yield mock_db

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/imports/999/status")

        app.dependency_overrides.clear()

        assert response.status_code == 404
