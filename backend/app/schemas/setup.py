"""Pydantic schemas for setup wizard API endpoints (Phase 5)."""

from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class SetupStatus(BaseModel):
    """Response for setup status check."""

    setup_complete: bool = Field(..., description="Whether initial setup is complete")
    user_count: int = Field(..., description="Number of registered users")


class InitialSetupRequest(BaseModel):
    """Request body for initial setup (first user creation)."""

    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    ftp_watts: Decimal | None = Field(None, gt=0, description="Initial FTP in watts")
