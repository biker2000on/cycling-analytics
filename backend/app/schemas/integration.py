"""Pydantic schemas for integration API endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class GarminConnectRequest(BaseModel):
    """Request body for connecting a Garmin Connect account."""

    email: str = Field(..., description="Garmin Connect email address")
    password: str = Field(..., description="Garmin Connect password")


class IntegrationStatusResponse(BaseModel):
    """Response body for integration status queries."""

    id: int
    provider: str
    sync_enabled: bool
    last_sync_at: datetime | None = None
    status: str
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
