"""Pydantic schemas for user settings API endpoints."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FtpSetting(BaseModel):
    """Request body for setting FTP."""

    ftp_watts: Decimal = Field(..., gt=0, description="Functional Threshold Power in watts")


class FtpResponse(BaseModel):
    """Response for FTP setting retrieval."""

    ftp_watts: Decimal = Field(..., description="Current FTP value in watts")
    ftp_method: str = Field("manual", description="How FTP was determined")
    updated_at: datetime | None = Field(None, description="When FTP was last updated")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Full user settings (Phase 4.5)
# ---------------------------------------------------------------------------


class UserSettingsResponse(BaseModel):
    """Full user settings response."""

    ftp_watts: Decimal | None = Field(None, description="Current FTP value in watts")
    ftp_method: str = Field("manual", description="How FTP was determined")
    preferred_threshold_method: str = Field(
        "manual", description="Preferred threshold estimation method"
    )
    calendar_start_day: int = Field(
        1, description="Calendar start day (1=Monday, 7=Sunday)"
    )
    weight_kg: Decimal | None = Field(None, description="Body weight in kg")
    date_of_birth: date | None = Field(None, description="Date of birth")
    unit_system: str = Field(
        "metric", description="Unit system preference (metric or imperial)"
    )

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    """Request body for updating user settings."""

    preferred_threshold_method: str | None = Field(
        None, description="Preferred threshold estimation method"
    )
    calendar_start_day: int | None = Field(
        None, ge=1, le=7, description="Calendar start day (1=Monday, 7=Sunday)"
    )
    weight_kg: Decimal | None = Field(
        None, gt=0, description="Body weight in kg"
    )
    date_of_birth: date | None = Field(
        None, description="Date of birth"
    )
    unit_system: str | None = Field(
        None, description="Unit system preference (metric or imperial)"
    )
