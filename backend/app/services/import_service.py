"""Import service — orchestrates FIT file upload processing.

Handles hash computation, duplicate detection, file storage,
activity record creation, and Celery task dispatch.
"""

import hashlib
from datetime import UTC, datetime

import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity, ActivitySource, ProcessingStatus
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
