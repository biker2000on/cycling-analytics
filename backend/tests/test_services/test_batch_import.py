"""Tests for the batch import service.

Covers: zip extraction, duplicate detection within batches,
corrupted file handling, directory path validation, and bulk multi-file upload.
"""

import io
import os
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.batch_import_service import (
    MAX_FILES_PER_BATCH,
    BatchFileResult,
    _compute_hash,
    _is_fit_file,
    _is_fit_filename,
    _validate_directory_path,
    extract_and_queue_zip,
    queue_multiple_files,
    scan_directory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fit_content(payload: bytes = b"\x00" * 100) -> bytes:
    """Build minimal content that passes FIT magic byte validation.

    FIT header: 12 bytes minimum, with ".FIT" at offset 8.
    """
    header = bytearray(12)
    header[0] = 12  # header size
    header[8:12] = b".FIT"
    return bytes(header) + payload


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Create an in-memory zip with the given filename->content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _make_upload_file(filename: str, content: bytes) -> MagicMock:
    """Create a mock UploadFile with async read."""
    mock = MagicMock()
    mock.filename = filename
    mock.read = AsyncMock(return_value=content)
    return mock


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


class TestIsFitFile:
    def test_valid_fit(self) -> None:
        assert _is_fit_file(_make_fit_content()) is True

    def test_too_short(self) -> None:
        assert _is_fit_file(b"\x00" * 5) is False

    def test_wrong_magic(self) -> None:
        data = bytearray(20)
        data[0] = 12
        data[8:12] = b"NOPE"
        assert _is_fit_file(bytes(data)) is False

    def test_empty(self) -> None:
        assert _is_fit_file(b"") is False


class TestIsFitFilename:
    def test_lowercase(self) -> None:
        assert _is_fit_filename("ride.fit") is True

    def test_uppercase(self) -> None:
        assert _is_fit_filename("RIDE.FIT") is True

    def test_mixed_case(self) -> None:
        assert _is_fit_filename("Ride.Fit") is True

    def test_not_fit(self) -> None:
        assert _is_fit_filename("data.csv") is False

    def test_no_extension(self) -> None:
        assert _is_fit_filename("fitfile") is False


class TestComputeHash:
    def test_deterministic(self) -> None:
        data = b"test data"
        assert _compute_hash(data) == _compute_hash(data)

    def test_different_data(self) -> None:
        assert _compute_hash(b"a") != _compute_hash(b"b")


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


class TestValidateDirectoryPath:
    def test_path_traversal_dots(self) -> None:
        with pytest.raises(ValueError, match="traversal"):
            _validate_directory_path("/some/path/../../../etc/passwd")

    def test_null_byte(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_directory_path("/some/path\x00malicious")

    def test_nonexistent_path(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            _validate_directory_path("/nonexistent/path/that/does/not/exist")

    def test_file_not_directory(self) -> None:
        """Passing a file path (not a directory) should fail."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="not a directory"):
                _validate_directory_path(temp_path)
        finally:
            os.unlink(temp_path)

    def test_valid_temp_directory(self) -> None:
        """A valid temporary directory should pass validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _validate_directory_path(tmpdir)
            assert result.is_dir()
            assert result.is_absolute()

    def test_sensitive_etc(self) -> None:
        """On systems where /etc exists, it should be blocked."""
        if Path("/etc").exists():
            with pytest.raises(ValueError, match="not allowed"):
                _validate_directory_path("/etc")

    def test_sensitive_windows(self) -> None:
        """On Windows, C:\\Windows should be blocked."""
        if Path("C:\\Windows").exists():
            with pytest.raises(ValueError, match="not allowed"):
                _validate_directory_path("C:\\Windows")


# ---------------------------------------------------------------------------
# Zip extraction
# ---------------------------------------------------------------------------


class TestExtractAndQueueZip:
    @pytest.mark.asyncio
    async def test_valid_zip_with_fit_files(self) -> None:
        """Zip with valid FIT files should create a batch and queue them."""
        fit_content_1 = _make_fit_content(b"\x01" * 50)
        fit_content_2 = _make_fit_content(b"\x02" * 50)

        zip_bytes = _make_zip({
            "rides/ride1.fit": fit_content_1,
            "rides/ride2.fit": fit_content_2,
        })

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
             patch("app.services.batch_import_service.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            batch, results = await extract_and_queue_zip(zip_bytes, 1, db)

        assert batch.total_files == 2
        assert len(results) == 2
        assert all(r.status == "pending" for r in results)

    @pytest.mark.asyncio
    async def test_zip_with_nested_garmin_structure(self) -> None:
        """Zip mimicking Garmin export structure should find nested .fit files."""
        fit_content = _make_fit_content(b"\x03" * 50)

        zip_bytes = _make_zip({
            "Garmin/Activities/2026-02-10/morning_ride.fit": fit_content,
            "Garmin/Activities/2026-02-09/evening_ride.fit": _make_fit_content(b"\x04" * 50),
            "Garmin/readme.txt": b"not a fit file",
        })

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
             patch("app.services.batch_import_service.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            batch, results = await extract_and_queue_zip(zip_bytes, 1, db)

        # Should only find .fit files, not the .txt
        assert batch.total_files == 2
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_zip_duplicate_detection(self) -> None:
        """Duplicate files within a batch should be skipped."""
        fit_content = _make_fit_content(b"\x05" * 50)

        # Two identical files
        zip_bytes = _make_zip({
            "ride1.fit": fit_content,
            "ride1_copy.fit": fit_content,
        })

        call_count = 0
        existing_activity = MagicMock()
        existing_activity.id = 42

        def mock_scalar_one_or_none() -> MagicMock | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # first file: no duplicate
            return existing_activity  # second file: duplicate found

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = mock_scalar_one_or_none

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
             patch("app.services.batch_import_service.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            batch, results = await extract_and_queue_zip(zip_bytes, 1, db)

        assert batch.total_files == 2
        assert batch.skipped_files == 1
        # One pending, one skipped
        statuses = {r.status for r in results}
        assert "pending" in statuses
        assert "skipped" in statuses

    @pytest.mark.asyncio
    async def test_zip_corrupted_files_still_process_others(self) -> None:
        """Corrupted FIT files should be marked as errors, others still process."""
        valid_fit = _make_fit_content(b"\x06" * 50)
        corrupted = b"this is not a fit file at all"

        zip_bytes = _make_zip({
            "good.fit": valid_fit,
            "bad.fit": corrupted,
        })

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
             patch("app.services.batch_import_service.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            batch, results = await extract_and_queue_zip(zip_bytes, 1, db)

        assert batch.total_files == 2
        assert batch.failed_files == 1
        # One pending (valid), one error (corrupted)
        error_results = [r for r in results if r.status == "error"]
        pending_results = [r for r in results if r.status == "pending"]
        assert len(error_results) == 1
        assert len(pending_results) == 1
        assert "Invalid FIT" in (error_results[0].error_message or "")

    @pytest.mark.asyncio
    async def test_invalid_zip(self) -> None:
        """Non-zip content should raise ValueError."""
        db = AsyncMock()
        with pytest.raises(ValueError, match="Invalid zip"):
            await extract_and_queue_zip(b"not a zip file", 1, db)

    @pytest.mark.asyncio
    async def test_empty_zip_no_fit_files(self) -> None:
        """Zip with no .fit files should raise ValueError."""
        zip_bytes = _make_zip({"readme.txt": b"no fit files here"})
        db = AsyncMock()
        with pytest.raises(ValueError, match="No .fit files"):
            await extract_and_queue_zip(zip_bytes, 1, db)


# ---------------------------------------------------------------------------
# Bulk multi-file upload
# ---------------------------------------------------------------------------


class TestQueueMultipleFiles:
    @pytest.mark.asyncio
    async def test_multiple_valid_files(self) -> None:
        """Multiple valid FIT files should all be queued."""
        files = [
            _make_upload_file("ride1.fit", _make_fit_content(b"\x10" * 50)),
            _make_upload_file("ride2.fit", _make_fit_content(b"\x11" * 50)),
        ]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
             patch("app.services.batch_import_service.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            batch, results = await queue_multiple_files(files, 1, db)

        assert batch.total_files == 2
        assert len(results) == 2
        assert all(r.status == "pending" for r in results)

    @pytest.mark.asyncio
    async def test_empty_files_list(self) -> None:
        """Empty file list should raise ValueError."""
        db = AsyncMock()
        with pytest.raises(ValueError, match="No files provided"):
            await queue_multiple_files([], 1, db)

    @pytest.mark.asyncio
    async def test_mix_of_valid_and_invalid(self) -> None:
        """Mix of valid and invalid files: invalid marked as error, valid queued."""
        files = [
            _make_upload_file("good.fit", _make_fit_content(b"\x20" * 50)),
            _make_upload_file("bad.fit", b"not a fit file"),
        ]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        db.add = MagicMock()

        with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
             patch("app.services.batch_import_service.celery_app") as mock_celery:
            mock_celery.send_task.return_value = MagicMock(id="task-123")

            batch, results = await queue_multiple_files(files, 1, db)

        assert batch.total_files == 2
        assert batch.failed_files == 1
        error_results = [r for r in results if r.status == "error"]
        assert len(error_results) == 1


# ---------------------------------------------------------------------------
# Directory scan
# ---------------------------------------------------------------------------


class TestScanDirectory:
    @pytest.mark.asyncio
    async def test_scan_valid_directory(self) -> None:
        """Directory with FIT files should create a batch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some FIT files
            fit1 = Path(tmpdir) / "ride1.fit"
            fit1.write_bytes(_make_fit_content(b"\x30" * 50))

            fit2 = Path(tmpdir) / "subdir" / "ride2.fit"
            fit2.parent.mkdir()
            fit2.write_bytes(_make_fit_content(b"\x31" * 50))

            db = AsyncMock()
            db.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            )
            db.flush = AsyncMock()
            db.add = MagicMock()

            with patch("app.services.batch_import_service.save_fit_file", return_value="1/2026/02/test.fit"), \
                 patch("app.services.batch_import_service.celery_app") as mock_celery:
                mock_celery.send_task.return_value = MagicMock(id="task-123")

                batch, results = await scan_directory(tmpdir, 1, db)

            assert batch.total_files == 2
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_scan_empty_directory(self) -> None:
        """Directory with no FIT files should raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = AsyncMock()
            with pytest.raises(ValueError, match="No .fit files"):
                await scan_directory(tmpdir, 1, db)

    @pytest.mark.asyncio
    async def test_scan_nonexistent_directory(self) -> None:
        """Nonexistent directory should raise ValueError."""
        db = AsyncMock()
        with pytest.raises(ValueError, match="does not exist"):
            await scan_directory("/nonexistent/path/xyz", 1, db)

    @pytest.mark.asyncio
    async def test_scan_path_traversal_blocked(self) -> None:
        """Path with traversal components should be blocked."""
        db = AsyncMock()
        with pytest.raises(ValueError, match="traversal"):
            await scan_directory("/tmp/../../../etc", 1, db)


# ---------------------------------------------------------------------------
# BatchFileResult
# ---------------------------------------------------------------------------


class TestBatchFileResult:
    def test_default_status(self) -> None:
        result = BatchFileResult("test.fit")
        assert result.filename == "test.fit"
        assert result.status == "pending"
        assert result.error_message is None
        assert result.activity_id is None
