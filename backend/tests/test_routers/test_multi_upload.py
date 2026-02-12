"""Tests for the multi-file upload endpoint POST /activities/upload."""

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as the_app
from app.models.activity import ActivitySource, ProcessingStatus
from app.services.import_service import DuplicateFileError


def _make_valid_fit_bytes() -> bytes:
    """Create minimal bytes that pass FIT magic validation."""
    header = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT"
    return header + b"\x00" * 100


def _make_fake_activity(activity_id: int = 1) -> SimpleNamespace:
    """Create a minimal fake Activity for mocking handle_upload return."""
    return SimpleNamespace(id=activity_id)


def _make_zip_with_fits(fit_files: dict[str, bytes]) -> bytes:
    """Create a zip archive in memory with the given filename->content pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in fit_files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    """Async HTTP test client."""
    transport = ASGITransport(app=the_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture(autouse=True)
def _clear_overrides() -> None:  # type: ignore[misc]
    """Ensure dependency overrides are cleared after each test."""
    yield  # type: ignore[misc]
    the_app.dependency_overrides.clear()


# -----------------------------------------------------------------------
# POST /activities/upload — multi-file upload
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_multiple_fit_files(client: AsyncClient) -> None:
    """Upload multiple .fit files returns array of results."""
    fit_content = _make_valid_fit_bytes()

    call_count = 0

    async def mock_upload_side_effect(file, db, user_id=1):
        nonlocal call_count
        call_count += 1
        return (_make_fake_activity(activity_id=call_count), f"task-{call_count}")

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = mock_upload_side_effect
        response = await client.post(
            "/activities/upload",
            files=[
                ("files", ("ride1.fit", io.BytesIO(fit_content), "application/octet-stream")),
                ("files", ("ride2.fit", io.BytesIO(fit_content), "application/octet-stream")),
            ],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0
    assert len(data["uploads"]) == 2
    assert data["uploads"][0]["activity_id"] == 1
    assert data["uploads"][1]["activity_id"] == 2


@pytest.mark.asyncio
async def test_upload_zip_containing_fit_files(client: AsyncClient) -> None:
    """Upload a .zip containing FIT files extracts and processes each."""
    fit_content = _make_valid_fit_bytes()
    zip_bytes = _make_zip_with_fits({
        "ride_a.fit": fit_content,
        "ride_b.fit": fit_content,
    })

    call_count = 0

    async def mock_upload_side_effect(file, db, user_id=1):
        nonlocal call_count
        call_count += 1
        return (_make_fake_activity(activity_id=10 + call_count), f"zip-task-{call_count}")

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = mock_upload_side_effect
        response = await client.post(
            "/activities/upload",
            files=[("files", ("rides.zip", io.BytesIO(zip_bytes), "application/zip"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0
    # Both entries should have activity_ids
    for upload in data["uploads"]:
        assert upload["activity_id"] is not None
        assert upload["task_id"] is not None


@pytest.mark.asyncio
async def test_zip_with_non_fit_files_returns_per_file_errors(client: AsyncClient) -> None:
    """.zip with non-FIT files returns per-file errors."""
    zip_bytes = _make_zip_with_fits({
        "readme.txt": b"hello world",
        "data.csv": b"a,b,c\n1,2,3",
    })

    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post(
            "/activities/upload",
            files=[("files", ("stuff.zip", io.BytesIO(zip_bytes), "application/zip"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 0
    assert data["failed"] == 2
    for upload in data["uploads"]:
        assert upload["error"] is not None
        assert "Unsupported" in upload["error"]


@pytest.mark.asyncio
async def test_zip_exceeding_max_files_rejected(client: AsyncClient) -> None:
    """.zip with >500 files is rejected entirely."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        fit_content = _make_valid_fit_bytes()
        for i in range(501):
            zf.writestr(f"ride_{i:04d}.fit", fit_content)
    zip_bytes = buf.getvalue()

    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post(
            "/activities/upload",
            files=[("files", ("huge.zip", io.BytesIO(zip_bytes), "application/zip"))],
        )

    assert response.status_code == 202
    data = response.json()
    # Entire zip rejected as single error
    assert data["total_files"] == 1
    assert data["failed"] == 1
    assert "501" in data["uploads"][0]["error"]
    assert "500" in data["uploads"][0]["error"]


@pytest.mark.asyncio
async def test_invalid_file_type_returns_error(client: AsyncClient) -> None:
    """Invalid file types (.txt, .csv, etc.) return error."""
    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post(
            "/activities/upload",
            files=[
                ("files", ("readme.txt", io.BytesIO(b"hello"), "text/plain")),
                ("files", ("data.csv", io.BytesIO(b"a,b"), "text/csv")),
            ],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 0
    assert data["failed"] == 2
    for upload in data["uploads"]:
        assert "Unsupported" in upload["error"]


@pytest.mark.asyncio
async def test_single_fit_through_multi_upload(client: AsyncClient) -> None:
    """Single .fit file works through multi-upload endpoint."""
    fit_content = _make_valid_fit_bytes()

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.return_value = (_make_fake_activity(activity_id=99), "single-task")
        response = await client.post(
            "/activities/upload",
            files=[("files", ("solo.fit", io.BytesIO(fit_content), "application/octet-stream"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 1
    assert data["successful"] == 1
    assert data["failed"] == 0
    assert data["uploads"][0]["activity_id"] == 99
    assert data["uploads"][0]["task_id"] == "single-task"


@pytest.mark.asyncio
async def test_empty_upload_returns_error(client: AsyncClient) -> None:
    """Empty upload (no files) returns 400."""
    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post("/activities/upload")

    assert response.status_code == 422  # FastAPI validation: missing required 'files'


@pytest.mark.asyncio
async def test_duplicate_fit_in_multi_upload(client: AsyncClient) -> None:
    """Duplicate file within multi-upload returns per-file error without failing others."""
    fit_content = _make_valid_fit_bytes()

    call_count = 0

    async def mock_upload_side_effect(file, db, user_id=1):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise DuplicateFileError(existing_activity_id=42)
        return (_make_fake_activity(activity_id=call_count), f"task-{call_count}")

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = mock_upload_side_effect
        response = await client.post(
            "/activities/upload",
            files=[
                ("files", ("ride1.fit", io.BytesIO(fit_content), "application/octet-stream")),
                ("files", ("ride2.fit", io.BytesIO(fit_content), "application/octet-stream")),
                ("files", ("ride3.fit", io.BytesIO(fit_content), "application/octet-stream")),
            ],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 3
    assert data["successful"] == 2
    assert data["failed"] == 1
    assert data["uploads"][0]["activity_id"] == 1
    assert "Duplicate" in data["uploads"][1]["error"]
    assert data["uploads"][2]["activity_id"] == 3


@pytest.mark.asyncio
async def test_zip_with_nested_zip_rejected(client: AsyncClient) -> None:
    """Nested zip files within a zip are rejected per-entry."""
    fit_content = _make_valid_fit_bytes()
    inner_zip = _make_zip_with_fits({"inner.fit": fit_content})
    zip_bytes = _make_zip_with_fits({
        "ride.fit": fit_content,
        "nested.zip": inner_zip,
    })

    call_count = 0

    async def mock_upload_side_effect(file, db, user_id=1):
        nonlocal call_count
        call_count += 1
        return (_make_fake_activity(activity_id=call_count), f"task-{call_count}")

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = mock_upload_side_effect
        response = await client.post(
            "/activities/upload",
            files=[("files", ("bundle.zip", io.BytesIO(zip_bytes), "application/zip"))],
        )

    assert response.status_code == 202
    data = response.json()
    # One success (ride.fit), one failure (nested.zip)
    assert data["successful"] == 1
    assert data["failed"] == 1
    errors = [u for u in data["uploads"] if u["error"] is not None]
    assert any("Nested" in e["error"] or "nested" in e["error"].lower() for e in errors)


@pytest.mark.asyncio
async def test_invalid_fit_magic_in_multi_upload(client: AsyncClient) -> None:
    """FIT file with invalid magic bytes returns per-file error."""
    bad_fit = b"this is not a FIT file at all, just random bytes" + b"\x00" * 100

    with patch("app.routers.activities._check_rate_limit", return_value=True):
        response = await client.post(
            "/activities/upload",
            files=[("files", ("bad.fit", io.BytesIO(bad_fit), "application/octet-stream"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["failed"] == 1
    assert "Invalid FIT" in data["uploads"][0]["error"] or "magic" in data["uploads"][0]["error"]


@pytest.mark.asyncio
async def test_rate_limit_on_multi_upload(client: AsyncClient) -> None:
    """Rate limit applies per request to multi-upload endpoint."""
    with patch("app.routers.activities._check_rate_limit", return_value=False):
        fit_content = _make_valid_fit_bytes()
        response = await client.post(
            "/activities/upload",
            files=[("files", ("ride.fit", io.BytesIO(fit_content), "application/octet-stream"))],
        )

    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


@pytest.mark.asyncio
async def test_mixed_fit_and_zip_upload(client: AsyncClient) -> None:
    """Mix of .fit and .zip files processes correctly."""
    fit_content = _make_valid_fit_bytes()
    zip_bytes = _make_zip_with_fits({"zipped_ride.fit": fit_content})

    call_count = 0

    async def mock_upload_side_effect(file, db, user_id=1):
        nonlocal call_count
        call_count += 1
        return (_make_fake_activity(activity_id=call_count), f"task-{call_count}")

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = mock_upload_side_effect
        response = await client.post(
            "/activities/upload",
            files=[
                ("files", ("direct.fit", io.BytesIO(fit_content), "application/octet-stream")),
                ("files", ("archive.zip", io.BytesIO(zip_bytes), "application/zip")),
            ],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_source_file_set_for_zip_upload(client: AsyncClient) -> None:
    """Zip upload sets source_file to the zip filename for all extracted entries."""
    fit_content = _make_valid_fit_bytes()
    zip_bytes = _make_zip_with_fits({
        "ride_a.fit": fit_content,
        "ride_b.fit": fit_content,
    })

    call_count = 0

    async def mock_upload_side_effect(file, db, user_id=1):
        nonlocal call_count
        call_count += 1
        return (_make_fake_activity(activity_id=call_count), f"task-{call_count}")

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.side_effect = mock_upload_side_effect
        response = await client.post(
            "/activities/upload",
            files=[("files", ("rides.zip", io.BytesIO(zip_bytes), "application/zip"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 2

    # Both extracted files should have source_file set to the zip filename
    for upload in data["uploads"]:
        assert upload["source_file"] == "rides.zip"
        assert upload["filename"] in ["ride_a.fit", "ride_b.fit"]


@pytest.mark.asyncio
async def test_source_file_set_for_direct_fit_upload(client: AsyncClient) -> None:
    """Direct .fit upload sets source_file to the .fit filename."""
    fit_content = _make_valid_fit_bytes()

    with (
        patch("app.services.import_service.handle_upload", new_callable=AsyncMock) as mock_upload,
        patch("app.routers.activities._check_rate_limit", return_value=True),
    ):
        mock_upload.return_value = (_make_fake_activity(activity_id=1), "task-1")
        response = await client.post(
            "/activities/upload",
            files=[("files", ("my_ride.fit", io.BytesIO(fit_content), "application/octet-stream"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["total_files"] == 1
    assert data["successful"] == 1

    # Direct upload should have source_file set to its own filename
    assert data["uploads"][0]["source_file"] == "my_ride.fit"
    assert data["uploads"][0]["filename"] == "my_ride.fit"
