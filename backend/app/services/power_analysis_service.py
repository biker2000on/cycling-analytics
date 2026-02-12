"""Power and HR analysis service for activity detail views (Phase 7).

Computes power distribution, peak efforts, advanced stats, and HR analysis
from raw stream data.
"""

from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.metrics import (
    HRAnalysisResponse,
    HRDistributionBin,
    HRZoneTime,
    PeakEffort,
    PowerAnalysisResponse,
    PowerAnalysisStats,
    PowerDistributionBin,
)
from app.schemas.stream import ZoneBlock, ZoneBlocksResponse
from app.utils.coggan_model import (
    ZONE_UPPER_BOUNDS,
    calculate_normalized_power,
    get_power_zone,
)
from app.utils.power_analysis import best_effort

logger = structlog.get_logger(__name__)

# Standard peak effort durations
PEAK_DURATIONS = [
    (5, "5 sec"),
    (30, "30 sec"),
    (60, "1 min"),
    (300, "5 min"),
    (600, "10 min"),
    (1200, "20 min"),
    (1800, "30 min"),
    (3600, "60 min"),
]

# HR zone model (5-zone): boundaries as fraction of max HR
HR_ZONE_BOUNDARIES = [
    (1, 0.0, 0.68, "Recovery"),
    (2, 0.68, 0.82, "Aerobic"),
    (3, 0.82, 0.87, "Tempo"),
    (4, 0.87, 0.92, "Threshold"),
    (5, 0.92, 1.00, "VO2max"),
]


def _to_decimal(value: float, places: int = 1) -> Decimal:
    """Round a float to the given decimal places and return as Decimal."""
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)


def _get_hr_zone(hr: int, max_hr: int) -> int:
    """Return the HR zone (1-5) for a given heart rate."""
    if max_hr <= 0:
        return 1
    ratio = hr / max_hr
    for zone, _low, high, _name in HR_ZONE_BOUNDARIES:
        if ratio < high:
            return zone
    return 5


async def _fetch_raw_streams(
    activity_id: int, db: AsyncSession
) -> tuple[list[int | None], list[int | None]]:
    """Fetch raw per-second power and HR data for an activity.

    Returns (power_list, hr_list) with None for missing values.
    """
    query = text(
        """
        SELECT power_watts, heart_rate
        FROM activity_streams
        WHERE activity_id = :activity_id
        ORDER BY timestamp
        """
    )
    result = await db.execute(query, {"activity_id": activity_id})
    rows = result.fetchall()

    power: list[int | None] = []
    heart_rate: list[int | None] = []
    for row in rows:
        power.append(row.power_watts)
        heart_rate.append(row.heart_rate)

    return power, heart_rate


def compute_zone_blocks(
    power_data: list[int | None],
    ftp: int,
    block_seconds: int = 30,
) -> list[ZoneBlock]:
    """Compute 30-second zone blocks from per-second power data.

    Each block is classified by the zone of its average power.
    """
    blocks: list[ZoneBlock] = []
    n = len(power_data)

    for start in range(0, n, block_seconds):
        end = min(start + block_seconds, n)
        segment = power_data[start:end]
        valid = [p for p in segment if p is not None]

        if not valid:
            # All-null block: classify as Z1 with 0 power
            blocks.append(
                ZoneBlock(
                    start_seconds=start,
                    end_seconds=end,
                    zone=1,
                    avg_power=Decimal("0"),
                )
            )
            continue

        avg = sum(valid) / len(valid)
        zone = get_power_zone(round(avg), ftp)
        blocks.append(
            ZoneBlock(
                start_seconds=start,
                end_seconds=end,
                zone=zone,
                avg_power=_to_decimal(avg),
            )
        )

    return blocks


def compute_power_distribution(
    power_data: list[int | None],
    ftp: int,
    bin_width: int = 10,
) -> list[PowerDistributionBin]:
    """Compute power distribution in bins of bin_width watts."""
    valid = [p for p in power_data if p is not None and p >= 0]
    if not valid:
        return []

    max_power = max(valid)
    num_bins = (max_power // bin_width) + 1
    bins: dict[int, int] = {}

    for p in valid:
        bin_idx = p // bin_width
        bins[bin_idx] = bins.get(bin_idx, 0) + 1

    result: list[PowerDistributionBin] = []
    for i in range(num_bins + 1):
        count = bins.get(i, 0)
        if count > 0:
            bin_start = i * bin_width
            bin_end = bin_start + bin_width
            mid_power = bin_start + bin_width // 2
            zone = get_power_zone(mid_power, ftp)
            result.append(
                PowerDistributionBin(
                    bin_start=bin_start,
                    bin_end=bin_end,
                    count=count,
                    zone=zone,
                )
            )

    return result


def compute_peak_efforts(
    power_data: list[int | None],
    weight_kg: float | None = None,
) -> list[PeakEffort]:
    """Compute best-average-power for standard durations."""
    results: list[PeakEffort] = []

    for dur_s, label in PEAK_DURATIONS:
        effort = best_effort(power_data, dur_s)
        if effort is not None:
            watts = effort[0]
            wpkg = (
                _to_decimal(float(watts) / weight_kg, 2)
                if weight_kg and weight_kg > 0
                else None
            )
            results.append(
                PeakEffort(
                    duration_seconds=dur_s,
                    duration_label=label,
                    power_watts=watts,
                    power_wpkg=wpkg,
                )
            )
        else:
            results.append(
                PeakEffort(
                    duration_seconds=dur_s,
                    duration_label=label,
                    power_watts=None,
                    power_wpkg=None,
                )
            )

    return results


def compute_power_stats(
    power_data: list[int | None],
    ftp: int,
    duration_seconds: int | None = None,
    weight_kg: float | None = None,
) -> PowerAnalysisStats:
    """Compute advanced power statistics."""
    valid = [p for p in power_data if p is not None]
    if not valid:
        return PowerAnalysisStats()

    np_result = calculate_normalized_power(power_data)
    np_watts = np_result.np_watts
    avg_power = np_result.avg_power
    max_power = max(valid)

    vi: Decimal | None = None
    if_val: Decimal | None = None
    tss_val: Decimal | None = None
    work_kj: Decimal | None = None
    wpkg: Decimal | None = None

    if np_watts and avg_power and float(avg_power) > 0:
        vi = _to_decimal(float(np_watts) / float(avg_power), 2)

    if np_watts and ftp > 0:
        if_val = _to_decimal(float(np_watts) / ftp, 2)

    if np_watts and if_val and ftp > 0 and duration_seconds and duration_seconds > 0:
        tss_val = _to_decimal(
            (duration_seconds * float(np_watts) * float(if_val))
            / (ftp * 3600)
            * 100,
            1,
        )

    # Work (kJ) = avg_power * duration / 1000
    if avg_power and duration_seconds and duration_seconds > 0:
        work_kj = _to_decimal(float(avg_power) * duration_seconds / 1000, 1)

    if avg_power and weight_kg and weight_kg > 0:
        wpkg = _to_decimal(float(avg_power) / weight_kg, 2)

    return PowerAnalysisStats(
        normalized_power=np_watts,
        avg_power=avg_power,
        max_power=max_power,
        variability_index=vi,
        intensity_factor=if_val,
        tss=tss_val,
        work_kj=work_kj,
        watts_per_kg=wpkg,
    )


def compute_hr_distribution(
    hr_data: list[int | None],
    bin_width: int = 5,
) -> list[HRDistributionBin]:
    """Compute HR distribution in bins of bin_width bpm."""
    valid = [h for h in hr_data if h is not None and h > 0]
    if not valid:
        return []

    max_hr = max(valid)
    num_bins = (max_hr // bin_width) + 1
    bins: dict[int, int] = {}

    for h in valid:
        bin_idx = h // bin_width
        bins[bin_idx] = bins.get(bin_idx, 0) + 1

    result: list[HRDistributionBin] = []
    for i in range(num_bins + 1):
        count = bins.get(i, 0)
        if count > 0:
            result.append(
                HRDistributionBin(
                    bin_start=i * bin_width,
                    bin_end=(i + 1) * bin_width,
                    count=count,
                )
            )

    return result


def compute_hr_time_in_zones(
    hr_data: list[int | None],
    max_hr_setting: int,
) -> list[HRZoneTime]:
    """Compute time spent in each HR zone."""
    zone_seconds = {z: 0 for z in range(1, 6)}

    for h in hr_data:
        if h is None or h <= 0:
            continue
        zone = _get_hr_zone(h, max_hr_setting)
        zone_seconds[zone] += 1

    result: list[HRZoneTime] = []
    for zone_num, low_frac, high_frac, name in HR_ZONE_BOUNDARIES:
        min_hr = round(max_hr_setting * low_frac)
        max_hr = round(max_hr_setting * high_frac)
        if zone_num == 5:
            max_hr = max_hr_setting
        result.append(
            HRZoneTime(
                zone=zone_num,
                name=name,
                min_hr=min_hr,
                max_hr=max_hr,
                seconds=zone_seconds[zone_num],
            )
        )

    return result


# ---------------------------------------------------------------------------
# High-level API functions called by routers
# ---------------------------------------------------------------------------


async def get_zone_blocks(
    activity_id: int,
    ftp: int,
    db: AsyncSession,
) -> ZoneBlocksResponse:
    """Compute 30-second zone blocks for an activity."""
    power_data, _ = await _fetch_raw_streams(activity_id, db)
    blocks = compute_zone_blocks(power_data, ftp)
    return ZoneBlocksResponse(
        activity_id=activity_id,
        ftp=ftp,
        blocks=blocks,
        total_blocks=len(blocks),
    )


async def get_power_analysis(
    activity_id: int,
    ftp: int,
    db: AsyncSession,
    weight_kg: float | None = None,
    duration_seconds: int | None = None,
) -> PowerAnalysisResponse:
    """Compute full power analysis for an activity."""
    power_data, _ = await _fetch_raw_streams(activity_id, db)

    distribution = compute_power_distribution(power_data, ftp)
    peak_efforts = compute_peak_efforts(power_data, weight_kg)
    stats = compute_power_stats(power_data, ftp, duration_seconds, weight_kg)

    return PowerAnalysisResponse(
        activity_id=activity_id,
        ftp=ftp,
        weight_kg=_to_decimal(weight_kg, 1) if weight_kg else None,
        distribution=distribution,
        peak_efforts=peak_efforts,
        stats=stats,
    )


async def get_hr_analysis(
    activity_id: int,
    max_hr_setting: int,
    db: AsyncSession,
) -> HRAnalysisResponse:
    """Compute full HR analysis for an activity."""
    _, hr_data = await _fetch_raw_streams(activity_id, db)

    valid_hr = [h for h in hr_data if h is not None and h > 0]
    avg_hr = round(sum(valid_hr) / len(valid_hr)) if valid_hr else None
    max_hr = max(valid_hr) if valid_hr else None
    min_hr = min(valid_hr) if valid_hr else None

    distribution = compute_hr_distribution(hr_data)
    time_in_zones = compute_hr_time_in_zones(hr_data, max_hr_setting)

    return HRAnalysisResponse(
        activity_id=activity_id,
        max_hr_setting=max_hr_setting,
        avg_hr=avg_hr,
        max_hr=max_hr,
        min_hr=min_hr,
        distribution=distribution,
        time_in_zones=time_in_zones,
    )
