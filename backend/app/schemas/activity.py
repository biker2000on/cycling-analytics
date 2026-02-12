"""Pydantic schemas for activity API endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ActivityResponse(BaseModel):
    """Single activity serialized for JSON responses."""

    id: int
    user_id: int
    external_id: str | None = None
    source: str
    activity_date: datetime
    name: str
    sport_type: str | None = None

    # Duration / distance
    duration_seconds: int | None = None
    distance_meters: Decimal | None = None
    elevation_gain_meters: Decimal | None = None

    # Power
    avg_power_watts: Decimal | None = None
    max_power_watts: Decimal | None = None

    # Heart rate
    avg_hr: int | None = None
    max_hr: int | None = None

    # Cadence
    avg_cadence: int | None = None

    # Calories
    calories: int | None = None

    # Derived metrics
    tss: Decimal | None = None
    np_watts: Decimal | None = None
    intensity_factor: Decimal | None = None

    # File / device
    fit_file_path: str | None = None
    device_name: str | None = None
    notes: str | None = None

    # Processing
    processing_status: str
    error_message: str | None = None
    file_hash: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    """Paginated list of activities."""

    items: list[ActivityResponse]
    total: int = Field(..., description="Total number of activities")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class ActivityUploadResponse(BaseModel):
    """Response returned after a successful FIT file upload."""

    activity_id: int = Field(..., description="ID of the created activity")
    task_id: str = Field(..., description="Celery task ID for tracking processing")


class ManualActivityCreate(BaseModel):
    """Schema for manually creating an activity without a FIT file."""

    activity_date: datetime
    name: str
    sport_type: str = "cycling"
    duration_seconds: int | None = None
    distance_meters: Decimal | None = None
    elevation_gain_meters: Decimal | None = None
    avg_power_watts: Decimal | None = None
    avg_hr: int | None = None
    avg_cadence: int | None = None
    calories: int | None = None
    notes: str | None = None


class FileUploadResult(BaseModel):
    """Result for a single file within a multi-upload."""

    filename: str
    activity_id: int | None = None
    task_id: str | None = None
    error: str | None = None


class MultiUploadResponse(BaseModel):
    """Response for multi-file upload endpoint."""

    uploads: list[FileUploadResult]
    total_files: int
    successful: int
    failed: int
