"""Batch import service -- handles zip archive, multi-file, and directory imports.

Orchestrates extraction, duplicate detection, file storage, batch record
creation, and Celery task dispatch for bulk FIT file imports.
"""

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.import_batch import ImportBatch, ImportBatchStatus
from app.services.storage_service import save_fit_file
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# FIT file magic bytes at offset 8
FIT_MAGIC_BYTES = b".FIT"
FIT_MAGIC_OFFSET = 8
MIN_FIT_HEADER_SIZE = 12

# Safety limits
MAX_ZIP_SIZE = 500 * 1024 * 1024  # 500 MB uncompressed
MAX_FILES_PER_BATCH = 500

# Allowed base directories for server-side directory import
ALLOWED_IMPORT_DIRS: list[str] = []  # Populated from settings or config


def _is_fit_file(content: bytes) -> bool:
    """Check if content has valid FIT magic bytes."""
    if len(content) < MIN_FIT_HEADER_SIZE:
        return False
    return content[FIT_MAGIC_OFFSET : FIT_MAGIC_OFFSET + 4] == FIT_MAGIC_BYTES


def _compute_hash(content: bytes) -> str:
    """Compute SHA256 hex digest of file content."""
    return hashlib.sha256(content).hexdigest()


def _is_fit_filename(filename: str) -> bool:
    """Check if filename has .fit extension (case-insensitive)."""
    return filename.lower().endswith(".fit")


def _validate_directory_path(path: str) -> Path:
    """Validate and resolve a directory path, preventing path traversal.

    Args:
        path: Directory path to validate.

    Returns:
        Resolved Path object.

    Raises:
        ValueError: If path is invalid, does not exist, or is outside allowed dirs.
    """
    settings = get_settings()

    # FIRST: reject path traversal and null bytes before any filesystem access
    if ".." in path:
        raise ValueError("Path contains invalid characters or traversal sequences")
    if "\x00" in path:
        raise ValueError("Path contains invalid characters or traversal sequences")

    # Resolve to absolute path (resolves symlinks, etc.)
    resolved = Path(path).resolve()

    # Must be absolute
    if not resolved.is_absolute():
        raise ValueError("Path must be absolute")

    # Path must exist and be a directory
    if not resolved.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    # Check that the resolved path doesn't point to sensitive system directories
    sensitive_dirs = ["/etc", "/var", "/sys", "/proc", "/root", "/boot"]
    # Windows sensitive dirs
    sensitive_dirs.extend(["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"])

    resolved_str = str(resolved)
    for sensitive in sensitive_dirs:
        if resolved_str.startswith(sensitive):
            raise ValueError(f"Access to {sensitive} is not allowed")

    return resolved


async def _check_duplicate(
    db: AsyncSession, file_hash: str, user_id: int
) -> Activity | None:
    """Check if a file with the given hash already exists for the user."""
    stmt = select(Activity).where(
        Activity.file_hash == file_hash,
        Activity.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _create_activity_and_queue(
    db: AsyncSession,
    content: bytes,
    filename: str,
    file_hash: str,
    user_id: int,
    batch_id: int,
) -> tuple[Activity, str]:
    """Save file, create Activity record, and queue Celery task.

    Returns:
        Tuple of (Activity, celery_task_id).
    """
    # Save file to disk
    file_path = save_fit_file(content, user_id)

    # Create Activity record
    activity = Activity(
        user_id=user_id,
        source=ActivitySource.fit_upload,
        activity_date=datetime.now(UTC),  # placeholder; updated after parsing
        name=filename or "Unnamed Activity",
        processing_status=ProcessingStatus.pending,
        fit_file_path=file_path,
        file_hash=file_hash,
    )
    db.add(activity)
    await db.flush()  # get the generated id

    # Queue Celery task on low_priority queue for batch imports
    task = celery_app.send_task(
        "app.workers.tasks.batch_import.process_batch_file",
        args=[batch_id, activity.id, file_path],
        queue="low_priority",
    )

    logger.info(
        "batch_file_queued",
        batch_id=batch_id,
        activity_id=activity.id,
        filename=filename,
        task_id=task.id,
    )

    return activity, task.id


class BatchFileResult:
    """Tracks the result of processing a single file within a batch."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.status: str = "pending"
        self.error_message: str | None = None
        self.activity_id: int | None = None


async def extract_and_queue_zip(
    zip_content: bytes,
    user_id: int,
    db: AsyncSession,
) -> tuple[ImportBatch, list[BatchFileResult]]:
    """Extract a zip archive and queue all .fit files for processing.

    Handles Garmin export directory structure (nested folders).
    Uses streaming extraction via zipfile module.

    Args:
        zip_content: Raw bytes of the zip file.
        user_id: Owner user ID.
        db: Async database session.

    Returns:
        Tuple of (ImportBatch, list of per-file results).

    Raises:
        ValueError: If zip is invalid or too large.
    """
    # Validate zip
    zip_buffer = io.BytesIO(zip_content)
    if not zipfile.is_zipfile(zip_buffer):
        raise ValueError("Invalid zip file")
    zip_buffer.seek(0)

    results: list[BatchFileResult] = []

    with zipfile.ZipFile(zip_buffer) as zf:
        # Collect all FIT files in the archive
        fit_entries = [
            info for info in zf.infolist()
            if not info.is_dir() and _is_fit_filename(info.filename)
        ]

        if not fit_entries:
            raise ValueError("No .fit files found in archive")

        if len(fit_entries) > MAX_FILES_PER_BATCH:
            raise ValueError(
                f"Too many files in archive ({len(fit_entries)}). "
                f"Maximum is {MAX_FILES_PER_BATCH}."
            )

        # Check total uncompressed size
        total_size = sum(info.file_size for info in fit_entries)
        if total_size > MAX_ZIP_SIZE:
            raise ValueError(
                f"Archive too large ({total_size / (1024 * 1024):.0f} MB uncompressed). "
                f"Maximum is {MAX_ZIP_SIZE // (1024 * 1024)} MB."
            )

        # Create batch record
        batch = ImportBatch(
            user_id=user_id,
            total_files=len(fit_entries),
            processed_files=0,
            failed_files=0,
            skipped_files=0,
            status=ImportBatchStatus.processing,
        )
        db.add(batch)
        await db.flush()

        logger.info(
            "zip_extraction_started",
            batch_id=batch.id,
            total_fit_files=len(fit_entries),
        )

        # Process each FIT file
        for info in fit_entries:
            file_result = BatchFileResult(
                filename=Path(info.filename).name
            )
            results.append(file_result)

            try:
                content = zf.read(info.filename)

                # Validate FIT magic bytes
                if not _is_fit_file(content):
                    file_result.status = "error"
                    file_result.error_message = "Invalid FIT file format"
                    batch.failed_files += 1
                    continue

                # Check for duplicate
                file_hash = _compute_hash(content)
                existing = await _check_duplicate(db, file_hash, user_id)
                if existing is not None:
                    file_result.status = "skipped"
                    file_result.error_message = (
                        f"Duplicate of activity {existing.id}"
                    )
                    file_result.activity_id = existing.id
                    batch.skipped_files += 1
                    continue

                # Save and queue
                activity, _task_id = await _create_activity_and_queue(
                    db, content, Path(info.filename).name, file_hash,
                    user_id, batch.id,
                )
                file_result.status = "pending"
                file_result.activity_id = activity.id

            except Exception as exc:
                logger.warning(
                    "batch_file_error",
                    filename=info.filename,
                    error=str(exc),
                )
                file_result.status = "error"
                file_result.error_message = str(exc)[:500]
                batch.failed_files += 1

        # If all files were skipped or failed, mark batch complete
        pending = batch.total_files - batch.failed_files - batch.skipped_files
        if pending == 0:
            batch.status = ImportBatchStatus.complete

        await db.flush()

    return batch, results


async def queue_multiple_files(
    files: list[UploadFile],
    user_id: int,
    db: AsyncSession,
) -> tuple[ImportBatch, list[BatchFileResult]]:
    """Process multiple uploaded FIT files as a batch.

    Args:
        files: List of uploaded FIT files.
        user_id: Owner user ID.
        db: Async database session.

    Returns:
        Tuple of (ImportBatch, list of per-file results).
    """
    if not files:
        raise ValueError("No files provided")

    if len(files) > MAX_FILES_PER_BATCH:
        raise ValueError(
            f"Too many files ({len(files)}). Maximum is {MAX_FILES_PER_BATCH}."
        )

    results: list[BatchFileResult] = []

    # Create batch record
    batch = ImportBatch(
        user_id=user_id,
        total_files=len(files),
        processed_files=0,
        failed_files=0,
        skipped_files=0,
        status=ImportBatchStatus.processing,
    )
    db.add(batch)
    await db.flush()

    for file in files:
        file_result = BatchFileResult(
            filename=file.filename or "unknown.fit"
        )
        results.append(file_result)

        try:
            content = await file.read()

            # Validate FIT magic bytes
            if not _is_fit_file(content):
                file_result.status = "error"
                file_result.error_message = "Invalid FIT file format"
                batch.failed_files += 1
                continue

            # Check for duplicate
            file_hash = _compute_hash(content)
            existing = await _check_duplicate(db, file_hash, user_id)
            if existing is not None:
                file_result.status = "skipped"
                file_result.error_message = f"Duplicate of activity {existing.id}"
                file_result.activity_id = existing.id
                batch.skipped_files += 1
                continue

            # Save and queue
            activity, _task_id = await _create_activity_and_queue(
                db, content, file.filename or "unknown.fit", file_hash,
                user_id, batch.id,
            )
            file_result.status = "pending"
            file_result.activity_id = activity.id

        except Exception as exc:
            logger.warning(
                "batch_file_error",
                filename=file.filename,
                error=str(exc),
            )
            file_result.status = "error"
            file_result.error_message = str(exc)[:500]
            batch.failed_files += 1

    # If all files were skipped or failed, mark batch complete
    pending = batch.total_files - batch.failed_files - batch.skipped_files
    if pending == 0:
        batch.status = ImportBatchStatus.complete

    await db.flush()

    return batch, results


async def scan_directory(
    path: str,
    user_id: int,
    db: AsyncSession,
) -> tuple[ImportBatch, list[BatchFileResult]]:
    """Scan a server-side directory for FIT files and queue them for import.

    IMPORTANT: Validates the path to prevent path traversal attacks.

    Args:
        path: Absolute path to directory containing FIT files.
        user_id: Owner user ID.
        db: Async database session.

    Returns:
        Tuple of (ImportBatch, list of per-file results).

    Raises:
        ValueError: If path is invalid or contains no FIT files.
    """
    # Validate path (prevents path traversal)
    resolved_dir = _validate_directory_path(path)

    # Find all .fit files recursively
    fit_files: list[Path] = sorted(
        p for p in resolved_dir.rglob("*.fit")
        if p.is_file()
    )
    # Also check .FIT extension (case-insensitive on case-sensitive filesystems)
    fit_files_upper: list[Path] = sorted(
        p for p in resolved_dir.rglob("*.FIT")
        if p.is_file() and p not in fit_files
    )
    fit_files.extend(fit_files_upper)

    if not fit_files:
        raise ValueError(f"No .fit files found in {path}")

    if len(fit_files) > MAX_FILES_PER_BATCH:
        raise ValueError(
            f"Too many files ({len(fit_files)}). Maximum is {MAX_FILES_PER_BATCH}."
        )

    results: list[BatchFileResult] = []

    # Create batch record
    batch = ImportBatch(
        user_id=user_id,
        total_files=len(fit_files),
        processed_files=0,
        failed_files=0,
        skipped_files=0,
        status=ImportBatchStatus.processing,
    )
    db.add(batch)
    await db.flush()

    logger.info(
        "directory_scan_started",
        batch_id=batch.id,
        directory=str(resolved_dir),
        total_fit_files=len(fit_files),
    )

    for fit_path in fit_files:
        file_result = BatchFileResult(filename=fit_path.name)
        results.append(file_result)

        try:
            content = fit_path.read_bytes()

            # Validate FIT magic bytes
            if not _is_fit_file(content):
                file_result.status = "error"
                file_result.error_message = "Invalid FIT file format"
                batch.failed_files += 1
                continue

            # Check for duplicate
            file_hash = _compute_hash(content)
            existing = await _check_duplicate(db, file_hash, user_id)
            if existing is not None:
                file_result.status = "skipped"
                file_result.error_message = f"Duplicate of activity {existing.id}"
                file_result.activity_id = existing.id
                batch.skipped_files += 1
                continue

            # Save and queue
            activity, _task_id = await _create_activity_and_queue(
                db, content, fit_path.name, file_hash,
                user_id, batch.id,
            )
            file_result.status = "pending"
            file_result.activity_id = activity.id

        except Exception as exc:
            logger.warning(
                "batch_file_error",
                filename=fit_path.name,
                error=str(exc),
            )
            file_result.status = "error"
            file_result.error_message = str(exc)[:500]
            batch.failed_files += 1

    # If all files were skipped or failed, mark batch complete
    pending = batch.total_files - batch.failed_files - batch.skipped_files
    if pending == 0:
        batch.status = ImportBatchStatus.complete

    await db.flush()

    return batch, results
