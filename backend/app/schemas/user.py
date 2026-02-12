"""Pydantic schemas for user profile API endpoints (Phase 5)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Full user profile response."""

    id: int
    email: str
    display_name: str
    weight_kg: Decimal | None = None
    date_of_birth: date | None = None
    timezone: str = "UTC"
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """Request body for updating user profile."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    weight_kg: Decimal | None = Field(None, gt=0, description="Body weight in kg")
    date_of_birth: date | None = Field(None, description="Date of birth")
    timezone: str | None = Field(None, max_length=50, description="IANA timezone")
