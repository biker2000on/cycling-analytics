"""Import service — orchestrates FIT file upload processing.

Handles hash computation, duplicate detection, file storage,
activity record creation, and Celery task dispatch.
"""

import hashlib
import io
import zipfile
from datetime import UTC, datetime

import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.schemas.activity import FileUploadResult
from app.services.storage_service import save_fit_file
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


class DuplicateFileError(Exception):
    """Raised when a FIT file with the same SHA256 hash already exists."""

    def __init__(self, existing_activity_id: int) -> None:
        self.existing_activity_id = existing_activity_id
        super().__init__(f"Duplicate file — matches activity {existing_activity_id}")


async def handle_upload(
    file: UploadFile,
    db: AsyncSession,
    user_id: int = 1,
) -> tuple[Activity, str]:
    """Process a FIT file upload end-to-end.

    1. Read file into memory and compute SHA256 hash.
    2. Check for duplicate (same hash already in DB).
    3. Save file to disk via storage_service.
    4. Create Activity record with status=pending.
    5. Queue Celery task for FIT parsing on high_priority queue.

    Args:
        file: The uploaded FIT file.
        db: Async database session.
        user_id: Owner user ID (default 1 for Phase 1).

    Returns:
        Tuple of (Activity, task_id string).

    Raises:
        DuplicateFileError: If a file with the same hash already exists.
    """
    # 1. Read content and compute hash
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    logger.info(
        "upload_received",
        filename=file.filename,
        size_bytes=len(content),
        file_hash=file_hash[:12],
    )

    # 2. Check for duplicate
    stmt = select(Activity).where(
        Activity.file_hash == file_hash,
        Activity.user_id == user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.warning(
            "duplicate_file_detected",
            file_hash=file_hash[:12],
            existing_activity_id=existing.id,
        )
        raise DuplicateFileError(existing.id)

    # 3. Save file to disk
    file_path = save_fit_file(content, user_id)

    # 4. Create Activity record
    activity = Activity(
        user_id=user_id,
        source=ActivitySource.fit_upload,
        activity_date=datetime.now(UTC),  # placeholder; updated after parsing
        name=file.filename or "Unnamed Activity",
        processing_status=ProcessingStatus.pending,
        fit_file_path=file_path,
        file_hash=file_hash,
    )
    db.add(activity)
    await db.flush()  # get the generated id

    logger.info(
        "activity_created",
        activity_id=activity.id,
        file_path=file_path,
    )

    # 5. Queue Celery task
    task = celery_app.send_task(
        "app.workers.tasks.fit_import.process_fit_upload",
        args=[activity.id, file_path],
        queue="high_priority",
    )

    logger.info(
        "celery_task_queued",
        activity_id=activity.id,
        task_id=task.id,
    )

    return activity, task.id


# ---------------------------------------------------------------------------
# Zip upload constants
# ---------------------------------------------------------------------------

ZIP_MAX_FILES = 500
ZIP_MAX_EXTRACTED_SIZE = 50 * 1024 * 1024  # 50 MB per extracted file
ZIP_READ_CHUNK_SIZE = 1024 * 1024  # 1 MB
ZIP_MAX_COMPRESSION_RATIO = 10

# FIT magic constants (duplicated here to avoid circular import from router)
_FIT_MAGIC_BYTES = b".FIT"
_FIT_MAGIC_OFFSET = 8
_MIN_FIT_HEADER_SIZE = 12


def _validate_fit_magic_bytes(content: bytes) -> bool:
    """Check if content has valid FIT magic bytes."""
    if len(content) < _MIN_FIT_HEADER_SIZE:
        return False
    return content[_FIT_MAGIC_OFFSET : _FIT_MAGIC_OFFSET + 4] == _FIT_MAGIC_BYTES


async def handle_zip_upload(
    zip_content: bytes,
    zip_filename: str,
    db: AsyncSession,
    user_id: int = 1,
) -> list[FileUploadResult]:
    """Extract FIT files from a zip archive and process each one.

    Safety limits:
    - Max 500 files per zip
    - Max 50 MB per extracted file (streaming enforcement)
    - No nested .zip files
    - Compression ratio > 10:1 skipped

    Args:
        zip_content: Raw bytes of the zip file.
        zip_filename: Original filename for logging.
        db: Async database session.
        user_id: Owner user ID.

    Returns:
        List of FileUploadResult for each entry processed.
    """
    results: list[FileUploadResult] = []

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_content))
    except zipfile.BadZipFile:
        return [FileUploadResult(filename=zip_filename, error="Invalid or corrupt zip file.")]

    entries = zf.infolist()

    # Safety: max file count
    if len(entries) > ZIP_MAX_FILES:
        return [
            FileUploadResult(
                filename=zip_filename,
                error=f"Zip contains {len(entries)} files, exceeding the limit of {ZIP_MAX_FILES}.",
            )
        ]

    for entry in entries:
        # Skip directories
        if entry.is_dir():
            continue

        entry_name = entry.filename
        lower_name = entry_name.lower()

        # Reject nested zips
        if lower_name.endswith(".zip"):
            results.append(
                FileUploadResult(filename=entry_name, error="Nested zip files are not allowed.")
            )
            continue

        # Only process .fit files
        if not lower_name.endswith(".fit"):
            results.append(
                FileUploadResult(filename=entry_name, error="Unsupported file type. Expected .fit file.")
            )
            continue

        # Check compression ratio
        compress_size = max(entry.compress_size, 1)
        if entry.file_size / compress_size > ZIP_MAX_COMPRESSION_RATIO:
            results.append(
                FileUploadResult(
                    filename=entry_name,
                    error="Compression ratio exceeds safety limit (10:1). Skipped.",
                )
            )
            continue

        # Extract with streaming size enforcement
        try:
            extracted = bytearray()
            with zf.open(entry) as ef:
                while True:
                    chunk = ef.read(ZIP_READ_CHUNK_SIZE)
                    if not chunk:
                        break
                    extracted.extend(chunk)
                    if len(extracted) > ZIP_MAX_EXTRACTED_SIZE:
                        raise ValueError("Extracted file exceeds 50 MB size limit.")
            content_bytes = bytes(extracted)
        except ValueError as exc:
            results.append(FileUploadResult(filename=entry_name, error=str(exc)))
            continue

        # Validate FIT magic
        if not _validate_fit_magic_bytes(content_bytes):
            results.append(
                FileUploadResult(filename=entry_name, error="Invalid FIT file (bad magic bytes).")
            )
            continue

        # Create an UploadFile-like object for handle_upload
        upload_file = StarletteUploadFile(
            file=io.BytesIO(content_bytes),
            filename=entry_name,
        )

        try:
            activity, task_id = await handle_upload(upload_file, db, user_id=user_id)
            results.append(
                FileUploadResult(
                    filename=entry_name,
                    activity_id=activity.id,
                    task_id=task_id,
                )
            )
        except DuplicateFileError as exc:
            results.append(
                FileUploadResult(
                    filename=entry_name,
                    error=f"Duplicate file. Already imported as activity {exc.existing_activity_id}.",
                )
            )
        except Exception as exc:
            logger.error("zip_entry_processing_failed", entry=entry_name, error=str(exc))
            results.append(
                FileUploadResult(filename=entry_name, error=f"Processing failed: {exc}")
            )

    zf.close()
    return results


async def handle_multi_upload(
    files: list[UploadFile],
    db: AsyncSession,
    user_id: int = 1,
) -> list[FileUploadResult]:
    """Orchestrate upload of multiple files (both .fit and .zip).

    Args:
        files: List of uploaded files.
        db: Async database session.
        user_id: Owner user ID.

    Returns:
        List of FileUploadResult for each file/entry processed.
    """
    results: list[FileUploadResult] = []

    for file in files:
        filename = file.filename or "unknown"
        lower_name = filename.lower()
        content = await file.read()

        # Size check
        if len(content) > ZIP_MAX_EXTRACTED_SIZE:
            results.append(
                FileUploadResult(
                    filename=filename,
                    error=f"File too large. Maximum size is {ZIP_MAX_EXTRACTED_SIZE // (1024 * 1024)} MB.",
                )
            )
            continue

        if lower_name.endswith(".zip"):
            zip_results = await handle_zip_upload(content, filename, db, user_id=user_id)
            results.extend(zip_results)
        elif lower_name.endswith(".fit"):
            # Validate FIT magic
            if not _validate_fit_magic_bytes(content):
                results.append(
                    FileUploadResult(filename=filename, error="Invalid FIT file (bad magic bytes).")
                )
                continue

            # Create UploadFile-like object with content
            upload_file = StarletteUploadFile(
                file=io.BytesIO(content),
                filename=filename,
            )

            try:
                activity, task_id = await handle_upload(upload_file, db, user_id=user_id)
                results.append(
                    FileUploadResult(
                        filename=filename,
                        activity_id=activity.id,
                        task_id=task_id,
                    )
                )
            except DuplicateFileError as exc:
                results.append(
                    FileUploadResult(
                        filename=filename,
                        error=f"Duplicate file. Already imported as activity {exc.existing_activity_id}.",
                    )
                )
            except Exception as exc:
                logger.error("file_processing_failed", filename=filename, error=str(exc))
                results.append(
                    FileUploadResult(filename=filename, error=f"Processing failed: {exc}")
                )
        else:
            results.append(
                FileUploadResult(
                    filename=filename,
                    error="Unsupported file type. Expected .fit or .zip file.",
                )
            )

    return results
