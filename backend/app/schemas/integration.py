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


# ---------------------------------------------------------------------------
# Strava schemas
# ---------------------------------------------------------------------------


class StravaAuthUrl(BaseModel):
    """Response containing the Strava OAuth2 authorization URL."""

    url: str


class StravaCallbackResponse(BaseModel):
    """Response after successful Strava OAuth2 callback."""

    connected: bool
    athlete_id: str


class StravaStatus(BaseModel):
    """Strava integration connection status."""

    connected: bool
    athlete_id: str | None = None
    last_sync: datetime | None = None
