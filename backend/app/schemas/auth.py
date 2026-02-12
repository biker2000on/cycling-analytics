"""Pydantic schemas for authentication API endpoints (Phase 5)."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name")


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="Password")


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str = Field(..., description="JWT refresh token")


class TokenResponse(BaseModel):
    """Response containing JWT tokens."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=1800, description="Access token expiry in seconds")


class UserResponse(BaseModel):
    """Public user information response."""

    id: int
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
