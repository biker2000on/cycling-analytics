"""Pydantic schemas for import batch API endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class ImportItemStatus(BaseModel):
    """Per-file status within a batch import."""

    filename: str
    status: str = Field(
        ..., description="One of: complete, skipped, error, pending"
    )
    error_message: str | None = None
    activity_id: int | None = None


class ImportBatchResponse(BaseModel):
    """Summary of an import batch."""

    id: int
    total_files: int
    processed_files: int
    failed_files: int
    skipped_files: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportBatchStatusResponse(ImportBatchResponse):
    """Detailed batch status including per-file breakdown."""

    items: list[ImportItemStatus] = Field(default_factory=list)


class DirectoryImportRequest(BaseModel):
    """Request body for server-side directory import."""

    path: str = Field(..., description="Absolute path to directory containing FIT files")
