"""Coggan power model — NP, IF, TSS, power zones.

Implements Dr. Andrew Coggan's training metrics used in TrainingPeaks,
WKO, and Golden Cheetah.

All numeric outputs use Decimal for precision (NUMERIC in database).
"""

from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from app.schemas.metrics import NormalizedPowerResult, PowerZoneDistribution

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLLING_WINDOW = 30  # 30-second rolling average for NP
MAX_REASONABLE_POWER = 2500  # watts — flag values above this
# Coggan power zone upper bounds (exclusive).
# Using integer percentage boundaries: Z1 <55%, Z2 55-75%, Z3 76-90%,
# Z4 91-105%, Z5 106-120%, Z6 121-150%, Z7 >150%.
# Upper bounds set at the start of the next zone (e.g. Z2 ends at 75%,
# Z3 starts at 76%, so Z2 upper is 0.76 exclusive).
ZONE_UPPER_BOUNDS: list[tuple[int, float]] = [
    (1, 0.55),
    (2, 0.76),
    (3, 0.91),
    (4, 1.06),
    (5, 1.21),
    (6, 1.51),
]


def _to_decimal(value: float, places: int = 1) -> Decimal:
    """Round a float to the given decimal places and return as Decimal."""
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Normalized Power
# ---------------------------------------------------------------------------


def calculate_normalized_power(
    power_data: list[int | None],
) -> NormalizedPowerResult:
    """Calculate Normalized Power from a list of 1-second power samples.

    Algorithm (Coggan):
        1. Calculate a 30-second rolling average of the power data
        2. Raise each averaged value to the 4th power
        3. Take the mean of those values
        4. Take the 4th root of the result

    Edge cases:
        - < 30 samples: returns average power with a warning
        - All nulls/empty: returns None with 'insufficient' confidence
        - > 2500 W spikes: flagged in warnings (included in calculation)
        - < 50% power coverage: 'low' confidence
    """
    if not power_data:
        return NormalizedPowerResult(
            np_watts=None,
            avg_power=None,
            confidence="insufficient",
            warnings=["No power data provided"],
        )

    warnings: list[str] = []

    # Filter out nulls but keep zeros (coasting)
    total_samples = len(power_data)
    valid_values = [p for p in power_data if p is not None]

    if not valid_values:
        return NormalizedPowerResult(
            np_watts=None,
            avg_power=None,
            confidence="insufficient",
            warnings=["All power values are null"],
        )

    # Coverage check
    coverage = len(valid_values) / total_samples
    confidence = "high"
    if coverage < 0.50:
        confidence = "low"
        warnings.append(
            f"Low power coverage: {coverage:.0%} of samples have data"
        )

    # Check for unreasonable spikes
    spike_count = sum(1 for v in valid_values if v > MAX_REASONABLE_POWER)
    if spike_count > 0:
        warnings.append(
            f"{spike_count} sample(s) exceed {MAX_REASONABLE_POWER}W — possible sensor error"
        )

    arr = np.array(valid_values, dtype=np.float64)
    avg_power = float(np.mean(arr))

    # Short ride: fewer than ROLLING_WINDOW valid samples
    if len(valid_values) < ROLLING_WINDOW:
        warnings.append(
            f"Ride shorter than {ROLLING_WINDOW}s — returning average power as NP"
        )
        return NormalizedPowerResult(
            np_watts=_to_decimal(avg_power),
            avg_power=_to_decimal(avg_power),
            confidence=confidence,
            warnings=warnings,
        )

    # 30-second rolling average using convolution
    kernel = np.ones(ROLLING_WINDOW) / ROLLING_WINDOW
    rolling_avg = np.convolve(arr, kernel, mode="valid")

    # Raise to the 4th power, mean, then 4th root
    fourth_power = rolling_avg**4
    np_value = float(np.mean(fourth_power) ** 0.25)

    return NormalizedPowerResult(
        np_watts=_to_decimal(np_value),
        avg_power=_to_decimal(avg_power),
        confidence=confidence,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Intensity Factor
# ---------------------------------------------------------------------------


def calculate_intensity_factor(np_watts: Decimal, ftp_watts: Decimal) -> Decimal:
    """Calculate Intensity Factor: IF = NP / FTP.

    Returns a Decimal rounded to 3 decimal places.
    """
    if ftp_watts <= 0:
        raise ValueError("FTP must be greater than zero")
    result = np_watts / ftp_watts
    return result.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Training Stress Score
# ---------------------------------------------------------------------------


def calculate_tss(
    duration_seconds: int,
    np_watts: Decimal,
    if_value: Decimal,
    ftp_watts: Decimal,
) -> Decimal:
    """Calculate Training Stress Score.

    Formula: TSS = (duration_seconds * NP * IF) / (FTP * 3600) * 100

    Returns a Decimal rounded to 1 decimal place.
    """
    if ftp_watts <= 0:
        raise ValueError("FTP must be greater than zero")
    if duration_seconds < 0:
        raise ValueError("Duration must be non-negative")

    numerator = Decimal(str(duration_seconds)) * np_watts * if_value
    denominator = ftp_watts * Decimal("3600")
    tss = (numerator / denominator) * Decimal("100")
    return tss.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def estimate_tss_from_avg_power(
    duration_seconds: int,
    avg_power: Decimal,
    ftp_watts: Decimal,
) -> Decimal:
    """Estimate TSS from average power (for manual entries without NP).

    Uses avg_power in place of NP, which underestimates TSS for variable
    efforts but is the best estimate without stream data.

    Formula: TSS = (duration * avg_power * (avg_power/FTP)) / (FTP * 3600) * 100
    """
    if ftp_watts <= 0:
        raise ValueError("FTP must be greater than zero")
    if duration_seconds < 0:
        raise ValueError("Duration must be non-negative")

    if_estimate = avg_power / ftp_watts
    numerator = Decimal(str(duration_seconds)) * avg_power * if_estimate
    denominator = ftp_watts * Decimal("3600")
    tss = (numerator / denominator) * Decimal("100")
    return tss.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Power Zones
# ---------------------------------------------------------------------------


def get_power_zone(power_watts: int, ftp_watts: int) -> int:
    """Return the Coggan power zone (1-7) for a given wattage.

    Zone boundaries (% of FTP):
        Z1: 0-54%    (Active Recovery)
        Z2: 55-75%   (Endurance)
        Z3: 76-90%   (Tempo)
        Z4: 91-105%  (Threshold)
        Z5: 106-120% (VO2max)
        Z6: 121-150% (Anaerobic)
        Z7: > 150%   (Neuromuscular)
    """
    if ftp_watts <= 0:
        raise ValueError("FTP must be greater than zero")

    ratio = power_watts / ftp_watts
    for zone, upper in ZONE_UPPER_BOUNDS:
        if ratio < upper:
            return zone
    return 7


def calculate_zone_distribution(
    power_data: list[int | None],
    ftp_watts: int,
) -> PowerZoneDistribution:
    """Calculate time spent in each Coggan power zone.

    Each entry in power_data is a 1-second sample. Nulls are excluded.
    Zeros are included and fall in Z1.
    """
    if ftp_watts <= 0:
        raise ValueError("FTP must be greater than zero")

    zone_seconds: dict[str, int] = {f"z{i}": 0 for i in range(1, 8)}
    total = 0

    for p in power_data:
        if p is None:
            continue
        zone = get_power_zone(p, ftp_watts)
        zone_seconds[f"z{zone}"] += 1
        total += 1

    return PowerZoneDistribution(zone_seconds=zone_seconds, total_seconds=total)
