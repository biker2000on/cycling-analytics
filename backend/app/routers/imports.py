"""Import API endpoints -- zip archive, bulk upload, directory import, batch status."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.activity import Activity, ProcessingStatus
from app.models.import_batch import ImportBatch
from app.schemas.import_batch import (
    DirectoryImportRequest,
    ImportBatchResponse,
    ImportBatchStatusResponse,
    ImportItemStatus,
)
from app.services.batch_import_service import (
    extract_and_queue_zip,
    queue_multiple_files,
    scan_directory,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])

DEFAULT_USER_ID = 1  # Phase 1: no auth, single seed user

MAX_ZIP_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/archive",
    response_model=ImportBatchStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a zip archive of FIT files",
)
async def upload_archive(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportBatchStatusResponse:
    """Accept a zip archive, extract .fit files, and queue them for processing.

    Handles Garmin export directory structure (nested folders).
    Returns batch ID and per-file status for tracking.
    """
    # Validate content type (allow zip and octet-stream)
    if file.content_type and file.content_type not in (
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected zip file, got {file.content_type}",
        )

    # Read zip content
    content = await file.read()

    if len(content) > MAX_ZIP_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_ZIP_UPLOAD_SIZE // (1024 * 1024)} MB.",
        )

    try:
        batch, results = await extract_and_queue_zip(content, DEFAULT_USER_ID, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ImportBatchStatusResponse(
        id=batch.id,
        total_files=batch.total_files,
        processed_files=batch.processed_files,
        failed_files=batch.failed_files,
        skipped_files=batch.skipped_files,
        status=batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        created_at=batch.created_at,
        items=[
            ImportItemStatus(
                filename=r.filename,
                status=r.status,
                error_message=r.error_message,
                activity_id=r.activity_id,
            )
            for r in results
        ],
    )


@router.post(
    "/bulk",
    response_model=ImportBatchStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload multiple FIT files at once",
)
async def upload_bulk(
    files: list[UploadFile],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportBatchStatusResponse:
    """Accept multiple FIT files in a single request and queue them for processing."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    try:
        batch, results = await queue_multiple_files(files, DEFAULT_USER_ID, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ImportBatchStatusResponse(
        id=batch.id,
        total_files=batch.total_files,
        processed_files=batch.processed_files,
        failed_files=batch.failed_files,
        skipped_files=batch.skipped_files,
        status=batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        created_at=batch.created_at,
        items=[
            ImportItemStatus(
                filename=r.filename,
                status=r.status,
                error_message=r.error_message,
                activity_id=r.activity_id,
            )
            for r in results
        ],
    )


@router.post(
    "/directory",
    response_model=ImportBatchStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import FIT files from a server-side directory",
)
async def import_directory(
    body: DirectoryImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportBatchStatusResponse:
    """Scan a server-side directory for FIT files and queue them for import.

    IMPORTANT: Path traversal prevention is enforced.
    """
    try:
        batch, results = await scan_directory(body.path, DEFAULT_USER_ID, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ImportBatchStatusResponse(
        id=batch.id,
        total_files=batch.total_files,
        processed_files=batch.processed_files,
        failed_files=batch.failed_files,
        skipped_files=batch.skipped_files,
        status=batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        created_at=batch.created_at,
        items=[
            ImportItemStatus(
                filename=r.filename,
                status=r.status,
                error_message=r.error_message,
                activity_id=r.activity_id,
            )
            for r in results
        ],
    )


@router.get(
    "/{batch_id}/status",
    response_model=ImportBatchStatusResponse,
    summary="Get batch import status",
)
async def get_batch_status(
    batch_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportBatchStatusResponse:
    """Return batch progress with per-file status.

    Reconstructs per-file status from the Activity records associated with
    the batch (via file_hash and timing).
    """
    # Fetch batch
    stmt = select(ImportBatch).where(
        ImportBatch.id == batch_id,
        ImportBatch.user_id == DEFAULT_USER_ID,
    )
    result = await db.execute(stmt)
    batch = result.scalar_one_or_none()

    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import batch {batch_id} not found.",
        )

    # Find all activities created around the same time as the batch
    # that were queued via this batch (approximation via created_at window)
    activities_stmt = select(Activity).where(
        Activity.user_id == DEFAULT_USER_ID,
        Activity.created_at >= batch.created_at,
    ).order_by(Activity.id)

    activities_result = await db.execute(activities_stmt)
    activities = activities_result.scalars().all()

    # Build per-file status items
    items: list[ImportItemStatus] = []
    for activity in activities:
        if activity.processing_status == ProcessingStatus.complete:
            file_status = "complete"
        elif activity.processing_status == ProcessingStatus.error:
            file_status = "error"
        elif activity.processing_status == ProcessingStatus.processing:
            file_status = "pending"
        else:
            file_status = "pending"

        items.append(
            ImportItemStatus(
                filename=activity.name,
                status=file_status,
                error_message=activity.error_message,
                activity_id=activity.id,
            )
        )

    return ImportBatchStatusResponse(
        id=batch.id,
        total_files=batch.total_files,
        processed_files=batch.processed_files,
        failed_files=batch.failed_files,
        skipped_files=batch.skipped_files,
        status=batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        created_at=batch.created_at,
        items=items,
    )
