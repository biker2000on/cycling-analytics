"""Tests for the import service."""

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.services.import_service import DuplicateFileError, handle_upload


def _make_upload_file(content: bytes, filename: str = "ride.fit") -> UploadFile:
    """Create a mock UploadFile with the given content."""
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


@pytest.mark.asyncio
async def test_handle_upload_creates_activity_and_queues_task() -> None:
    """handle_upload should save file, create Activity, and queue Celery task."""
    content = b"fake fit content"
    expected_hash = hashlib.sha256(content).hexdigest()

    upload_file = _make_upload_file(content)

    # Mock DB session
    mock_db = AsyncMock()

    # No duplicate found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock flush to set activity.id
    async def _fake_flush() -> None:
        # Find the Activity that was added to the session
        for call in mock_db.add.call_args_list:
            activity = call[0][0]
            if isinstance(activity, Activity):
                activity.id = 42

    mock_db.flush = AsyncMock(side_effect=_fake_flush)

    # Mock Celery task
    mock_task = MagicMock()
    mock_task.id = "task-abc-123"

    with (
        patch("app.services.import_service.save_fit_file", return_value="1/2026/02/test.fit"),
        patch("app.services.import_service.celery_app") as mock_celery,
    ):
        mock_celery.send_task.return_value = mock_task

        activity, task_id = await handle_upload(upload_file, mock_db, user_id=1)

    # Verify Activity was added
    mock_db.add.assert_called_once()
    added_activity = mock_db.add.call_args[0][0]
    assert isinstance(added_activity, Activity)
    assert added_activity.source == ActivitySource.fit_upload
    assert added_activity.processing_status == ProcessingStatus.pending
    assert added_activity.file_hash == expected_hash
    assert added_activity.fit_file_path == "1/2026/02/test.fit"

    # Verify task was queued
    assert task_id == "task-abc-123"
    mock_celery.send_task.assert_called_once_with(
        "app.workers.tasks.fit_import.process_fit_upload",
        args=[42, "1/2026/02/test.fit"],
        queue="high_priority",
    )


@pytest.mark.asyncio
async def test_handle_upload_rejects_duplicate() -> None:
    """handle_upload should raise DuplicateFileError for duplicate file hash."""
    content = b"duplicate content"
    upload_file = _make_upload_file(content)

    # Mock DB session — duplicate found
    existing_activity = MagicMock()
    existing_activity.id = 99

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_activity

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(DuplicateFileError) as exc_info:
        await handle_upload(upload_file, mock_db, user_id=1)

    assert exc_info.value.existing_activity_id == 99


@pytest.mark.asyncio
async def test_handle_upload_uses_filename_as_name() -> None:
    """handle_upload should use the uploaded filename as the activity name."""
    content = b"some content"
    upload_file = _make_upload_file(content, filename="morning_ride.fit")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()

    mock_task = MagicMock()
    mock_task.id = "task-xyz"

    with (
        patch("app.services.import_service.save_fit_file", return_value="1/2026/02/x.fit"),
        patch("app.services.import_service.celery_app") as mock_celery,
    ):
        mock_celery.send_task.return_value = mock_task
        await handle_upload(upload_file, mock_db, user_id=1)

    added_activity = mock_db.add.call_args[0][0]
    assert added_activity.name == "morning_ride.fit"
