"""Pydantic schemas for Coggan power-based metrics."""

from decimal import Decimal

from pydantic import BaseModel, Field


class NormalizedPowerResult(BaseModel):
    """Result of normalized power calculation."""

    np_watts: Decimal | None = Field(
        None, description="Normalized Power in watts (None if insufficient data)"
    )
    avg_power: Decimal | None = Field(
        None, description="Average power in watts (excluding nulls)"
    )
    confidence: str = Field(
        "high", description="Confidence level: high, low, or insufficient"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings about the data quality"
    )


class PowerZoneDistribution(BaseModel):
    """Time distribution across Coggan power zones."""

    zone_seconds: dict[str, int] = Field(
        ..., description="Seconds spent in each zone (keys: z1..z7)"
    )
    total_seconds: int = Field(
        ..., description="Total seconds with valid power data"
    )
