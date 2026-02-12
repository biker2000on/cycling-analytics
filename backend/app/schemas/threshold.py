"""Pydantic schemas for threshold management API endpoints."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ThresholdCreate(BaseModel):
    """Request body for creating a new threshold entry."""

    method: str = Field(..., description="Threshold method (manual, pct_20min, pct_8min)")
    ftp_watts: Decimal = Field(..., gt=0, description="FTP value in watts")
    effective_date: date = Field(..., description="Date the threshold takes effect")
    notes: str | None = Field(None, description="Optional notes about the threshold")


class ThresholdResponse(BaseModel):
    """Response for a single threshold entry."""

    id: int
    method: str
    ftp_watts: Decimal
    effective_date: date
    source_activity_id: int | None = None
    is_active: bool = True
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ThresholdHistory(BaseModel):
    """Response for threshold history listing."""

    thresholds: list[ThresholdResponse] = Field(
        default_factory=list, description="List of threshold entries"
    )
