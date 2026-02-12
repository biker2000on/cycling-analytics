"""Pydantic schemas for user settings API endpoints."""

from datetime import datetime
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
