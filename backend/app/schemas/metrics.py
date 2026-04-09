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


# ---------------------------------------------------------------------------
# Period Summary
# ---------------------------------------------------------------------------


class PeriodSummary(BaseModel):
    """Aggregated metrics for a date range."""

    total_tss: Decimal = Field(Decimal("0"), description="Sum of TSS across all rides")
    ride_count: int = Field(0, description="Number of rides in the period")
    total_duration_seconds: int = Field(0, description="Total ride duration in seconds")
    total_distance_meters: Decimal = Field(
        Decimal("0"), description="Total distance in meters"
    )
    start_date: date
    end_date: date


# ---------------------------------------------------------------------------
# Power Analysis (Plan 7.2)
# ---------------------------------------------------------------------------


class PowerDistributionBin(BaseModel):
    """A single 10-watt bin in the power distribution histogram."""

    bin_start: int = Field(..., description="Lower bound of the 10W bin")
    bin_end: int = Field(..., description="Upper bound of the 10W bin")
    count: int = Field(..., description="Number of seconds in this bin")
    zone: int = Field(..., ge=1, le=7, description="Power zone for this bin")


class PeakEffort(BaseModel):
    """Best average power for a given duration."""

    duration_seconds: int = Field(..., description="Duration in seconds")
    duration_label: str = Field(..., description="Human-readable label (e.g. '5 min')")
    power_watts: Decimal | None = Field(None, description="Best average power")
    power_wpkg: Decimal | None = Field(None, description="Best power in W/kg")


class PowerAnalysisStats(BaseModel):
    """Advanced power statistics for an activity."""

    normalized_power: Decimal | None = None
    avg_power: Decimal | None = None
    max_power: int | None = None
    variability_index: Decimal | None = None
    intensity_factor: Decimal | None = None
    tss: Decimal | None = None
    work_kj: Decimal | None = None
    watts_per_kg: Decimal | None = None


class PowerAnalysisResponse(BaseModel):
    """Full power analysis for an activity."""

    activity_id: int
    ftp: int
    weight_kg: Decimal | None = None
    distribution: list[PowerDistributionBin] = Field(default_factory=list)
    peak_efforts: list[PeakEffort] = Field(default_factory=list)
    stats: PowerAnalysisStats = Field(default_factory=PowerAnalysisStats)


# ---------------------------------------------------------------------------
# HR Analysis (Plan 7.3)
# ---------------------------------------------------------------------------


class HRDistributionBin(BaseModel):
    """A single 5-bpm bin in the HR distribution histogram."""

    bin_start: int = Field(..., description="Lower bound of the 5 bpm bin")
    bin_end: int = Field(..., description="Upper bound of the 5 bpm bin")
    count: int = Field(..., description="Number of seconds in this bin")


class HRZoneTime(BaseModel):
    """Time spent in a single HR zone."""

    zone: int = Field(..., ge=1, le=5, description="HR zone (1-5)")
    name: str = Field(..., description="Zone name")
    min_hr: int = Field(..., description="Lower HR bound")
    max_hr: int = Field(..., description="Upper HR bound")
    seconds: int = Field(..., description="Seconds in this zone")


class HRAnalysisResponse(BaseModel):
    """Full HR analysis for an activity."""

    activity_id: int
    max_hr_setting: int = Field(..., description="Max HR used for zone calculation")
    avg_hr: int | None = None
    max_hr: int | None = None
    min_hr: int | None = None
    distribution: list[HRDistributionBin] = Field(default_factory=list)
    time_in_zones: list[HRZoneTime] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Power Curve (Plan 8.2)
# ---------------------------------------------------------------------------


class PowerCurvePoint(BaseModel):
    """Single point on the power duration curve."""

    duration_seconds: int = Field(..., description="Duration in seconds")
    power_watts: Decimal = Field(..., description="Best average power for this duration")
    activity_id: int = Field(..., description="Source activity ID for this best effort")
    activity_date: date = Field(..., description="Date of the source activity")


class PowerCurveResponse(BaseModel):
    """Mean-max power curve across all activities in a date range."""

    data: list[PowerCurvePoint] = Field(default_factory=list)
    start_date: date
    end_date: date


# ---------------------------------------------------------------------------
# Calendar (Plan 8.3)
# ---------------------------------------------------------------------------


class CalendarActivity(BaseModel):
    """Individual activity summary for calendar display."""

    id: int
    name: str
    sport_type: str | None = None
    duration_seconds: int | None = None
    distance_meters: Decimal | None = None
    tss: Decimal | None = None
    elevation_gain_meters: Decimal | None = None
    avg_power_watts: Decimal | None = None
    avg_hr: int | None = None
    intensity_factor: Decimal | None = None

    model_config = {"from_attributes": True}


class CalendarDay(BaseModel):
    """Summary of activities for a single day, with individual activity details."""

    date: date
    activity_count: int = Field(0, description="Number of activities on this day")
    total_tss: Decimal = Field(Decimal("0"), description="Sum of TSS for the day")
    total_duration_seconds: int = Field(0, description="Total duration in seconds")
    total_distance_meters: Decimal = Field(Decimal("0"), description="Total distance in meters")
    activities: list[CalendarActivity] = Field(default_factory=list, description="Individual activities")


class CalendarMonth(BaseModel):
    """Calendar data for a month."""

    year: int
    month: int
    days: list[CalendarDay] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Totals (Plan 8.4)
# ---------------------------------------------------------------------------


class TotalsPeriod(BaseModel):
    """Aggregated totals for a single period (week/month/year)."""

    period_label: str = Field(..., description="Human label for the period (e.g. '2024-W03', 'Jan 2024')")
    period_start: date
    period_end: date
    ride_count: int = Field(0)
    total_tss: Decimal = Field(Decimal("0"))
    total_duration_seconds: int = Field(0)
    total_distance_meters: Decimal = Field(Decimal("0"))


class TotalsResponse(BaseModel):
    """Aggregated totals over multiple periods."""

    periods: list[TotalsPeriod] = Field(default_factory=list)
    period_type: str = Field(..., description="weekly, monthly, or yearly")
    start_date: date
    end_date: date
