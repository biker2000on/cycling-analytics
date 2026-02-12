"""Pydantic schemas for Coggan power-based metrics."""

from datetime import date, datetime
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


# ---------------------------------------------------------------------------
# Fitness (CTL / ATL / TSB)
# ---------------------------------------------------------------------------


class FitnessDataPoint(BaseModel):
    """Single day of fitness data."""

    date: date
    tss_total: Decimal = Field(..., description="Total TSS for the day")
    ctl: Decimal = Field(..., description="Chronic Training Load (fitness)")
    atl: Decimal = Field(..., description="Acute Training Load (fatigue)")
    tsb: Decimal = Field(..., description="Training Stress Balance (form)")


class FitnessTimeSeries(BaseModel):
    """Time-series fitness data for a date range."""

    data: list[FitnessDataPoint] = Field(..., description="Daily fitness data points")
    start_date: date
    end_date: date
    threshold_method: str = Field("manual", description="Threshold method used")


# ---------------------------------------------------------------------------
# Activity Metrics Response
# ---------------------------------------------------------------------------


class ActivityMetricsResponse(BaseModel):
    """Computed metrics for a single activity."""

    activity_id: int
    normalized_power: Decimal | None = None
    tss: Decimal | None = None
    intensity_factor: Decimal | None = None
    zone_distribution: dict | None = None
    variability_index: Decimal | None = None
    efficiency_factor: Decimal | None = None
    ftp_at_computation: Decimal
    threshold_method: str = "manual"
    computed_at: datetime

    model_config = {"from_attributes": True}
