"""Activity API endpoints — upload, list, detail, delete, export."""

import csv
import io
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_current_user_or_default, get_db
from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.activity_lap import ActivityLap
from app.models.activity_stream import ActivityStream
from app.models.user import User
from app.schemas.activity import (
    ActivityListResponse,
    ActivityResponse,
    ActivityUploadResponse,
    ManualActivityCreate,
)
from app.schemas.csv_import import CsvImportResponse
from app.services.csv_import_service import parse_and_import_csv
from app.services.import_service import DuplicateFileError, handle_upload
from app.services.storage_service import delete_fit_file

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/activities", tags=["activities"])

# ---------------------------------------------------------------------------
# FIT file magic bytes: first byte is the header size (usually 12 or 14),
# and bytes 8-11 are ".FIT" in ASCII. We check bytes at offset 8.
# For minimal validation, we check byte 0 is a valid header size (12 or 14)
# and that the file is at least 12 bytes.
# ---------------------------------------------------------------------------

FIT_MAGIC_BYTES = b".FIT"
FIT_MAGIC_OFFSET = 8
MIN_FIT_HEADER_SIZE = 12
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter: {ip: [timestamps]}
# ---------------------------------------------------------------------------

RATE_LIMIT_MAX_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 3600

_upload_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request is within the rate limit, False otherwise."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    # Prune old timestamps
    timestamps = _upload_timestamps[client_ip]
    _upload_timestamps[client_ip] = [ts for ts in timestamps if ts > cutoff]

    if len(_upload_timestamps[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    _upload_timestamps[client_ip].append(now)
    return True


def _validate_fit_magic(content: bytes) -> bool:
    """Check if the file content has valid FIT magic bytes.

    FIT files have ".FIT" at byte offset 8-11.
    """
    if len(content) < MIN_FIT_HEADER_SIZE:
        return False
    return content[FIT_MAGIC_OFFSET : FIT_MAGIC_OFFSET + 4] == FIT_MAGIC_BYTES


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/upload-fit",
    response_model=ActivityUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a FIT file for processing",
)
async def upload_fit(
    request: Request,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> ActivityUploadResponse:
    """Accept a multipart FIT file upload.

    Validates file size, FIT magic bytes, and rate limit.
    On success, returns 202 with activity_id and task_id for tracking.
    """
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit check
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 20 uploads per hour.",
        )

    # Read file content
    content = await file.read()

    # File size check
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB.",
        )

    # FIT magic bytes check
    if not _validate_fit_magic(content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Expected a valid FIT file.",
        )

    # Reset file position so handle_upload can read it again
    await file.seek(0)

    try:
        activity, task_id = await handle_upload(file, db, user_id=current_user.id)
    except DuplicateFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate file. Already imported as activity {exc.existing_activity_id}.",
        )

    return ActivityUploadResponse(activity_id=activity.id, task_id=task_id)


@router.get(
    "",
    response_model=ActivityListResponse,
    summary="List activities (paginated)",
)
async def list_activities(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> ActivityListResponse:
    """Return a paginated list of activities sorted by activity_date DESC."""
    # Count total
    count_stmt = select(func.count()).select_from(Activity).where(
        Activity.user_id == current_user.id
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Fetch page
    stmt = (
        select(Activity)
        .where(Activity.user_id == current_user.id)
        .order_by(Activity.activity_date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    activities = result.scalars().all()

    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/export-csv",
    summary="Export activities as CSV",
)
async def export_activities_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
    start_date: datetime | None = Query(default=None, description="Filter: start date (inclusive)"),
    end_date: datetime | None = Query(default=None, description="Filter: end date (inclusive)"),
) -> StreamingResponse:
    """Export a CSV file of activity summaries.

    Supports optional date range filtering via ``start_date`` and ``end_date``.
    """
    stmt = select(Activity).where(Activity.user_id == current_user.id)

    if start_date is not None:
        stmt = stmt.where(Activity.activity_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Activity.activity_date <= end_date)

    stmt = stmt.order_by(Activity.activity_date.desc())
    result = await db.execute(stmt)
    activities = result.scalars().all()

    columns = [
        "date",
        "name",
        "sport_type",
        "duration_seconds",
        "distance_meters",
        "avg_power_watts",
        "max_power_watts",
        "avg_hr",
        "max_hr",
        "tss",
        "np_watts",
        "intensity_factor",
        "source",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)

    for a in activities:
        writer.writerow([
            a.activity_date.isoformat() if a.activity_date else "",
            a.name or "",
            a.sport_type or "",
            a.duration_seconds if a.duration_seconds is not None else "",
            str(a.distance_meters) if a.distance_meters is not None else "",
            str(a.avg_power_watts) if a.avg_power_watts is not None else "",
            str(a.max_power_watts) if a.max_power_watts is not None else "",
            a.avg_hr if a.avg_hr is not None else "",
            a.max_hr if a.max_hr is not None else "",
            str(a.tss) if a.tss is not None else "",
            str(a.np_watts) if a.np_watts is not None else "",
            str(a.intensity_factor) if a.intensity_factor is not None else "",
            a.source.value if a.source else "",
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="activities.csv"',
        },
    )


@router.get(
    "/{activity_id}",
    response_model=ActivityResponse,
    summary="Get activity detail",
)
async def get_activity(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> ActivityResponse:
    """Return a single activity by ID."""
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )

    return ActivityResponse.model_validate(activity)


@router.get(
    "/{activity_id}/fit-file",
    summary="Download the original FIT file",
)
async def download_fit_file(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> FileResponse:
    """Return the original FIT file as a binary download.

    Returns 404 if the activity has no FIT file (e.g. manual entry).
    """
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )

    if not activity.fit_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} has no FIT file (manual entry).",
        )

    settings = get_settings()
    full_path = Path(settings.FIT_STORAGE_PATH) / activity.fit_file_path

    if not full_path.exists():
        logger.error(
            "fit_file_missing_on_disk",
            activity_id=activity_id,
            path=str(full_path),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FIT file not found on disk.",
        )

    return FileResponse(
        path=str(full_path),
        media_type="application/octet-stream",
        filename=f"activity_{activity_id}.fit",
    )


@router.delete(
    "/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an activity",
)
async def delete_activity(
    activity_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> None:
    """Delete an activity and its associated streams, laps, and FIT file."""
    # Fetch activity
    stmt = select(Activity).where(
        Activity.id == activity_id,
        Activity.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()

    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )

    # Delete related streams and laps explicitly (cascade should handle this,
    # but being explicit for clarity and TimescaleDB hypertable compatibility)
    await db.execute(
        delete(ActivityStream).where(ActivityStream.activity_id == activity_id)
    )
    await db.execute(
        delete(ActivityLap).where(ActivityLap.activity_id == activity_id)
    )

    # Delete FIT file from disk
    if activity.fit_file_path:
        delete_fit_file(activity.fit_file_path)

    # Delete activity record
    await db.delete(activity)

    logger.info("activity_deleted", activity_id=activity_id)


@router.post(
    "/manual",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual activity entry",
)
async def create_manual_activity(
    data: ManualActivityCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> ActivityResponse:
    """Create a manual activity entry (no FIT file).

    Manual activities are immediately marked as complete and require no further processing.
    """
    activity = Activity(
        user_id=current_user.id,
        source=ActivitySource.manual,
        activity_date=data.activity_date,
        name=data.name,
        sport_type=data.sport_type,
        duration_seconds=data.duration_seconds,
        distance_meters=data.distance_meters,
        elevation_gain_meters=data.elevation_gain_meters,
        avg_power_watts=data.avg_power_watts,
        avg_hr=data.avg_hr,
        avg_cadence=data.avg_cadence,
        calories=data.calories,
        notes=data.notes,
        processing_status=ProcessingStatus.complete,
    )
    db.add(activity)
    await db.flush()

    logger.info(
        "manual_activity_created",
        activity_id=activity.id,
        name=data.name,
    )

    return ActivityResponse.model_validate(activity)


@router.post(
    "/import-csv",
    response_model=CsvImportResponse,
    summary="Import activities from CSV",
)
async def import_csv(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_default)],
) -> CsvImportResponse:
    """Import activities from a CSV file.

    Expected CSV columns: date, name, sport_type, duration_minutes,
    distance_km, avg_power_watts, avg_hr, elevation_gain_m, notes.
    """
    content = await file.read()

    # File size check (10 MB limit for CSV)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="CSV file too large. Maximum size is 10 MB.",
        )

    return await parse_and_import_csv(content, current_user.id, db)
