"""Power analysis utilities -- best efforts and mean-max power curves.

Implements sliding-window best-effort calculations for threshold estimation.
All numeric outputs use Decimal for precision (NUMERIC in database).
"""

from decimal import ROUND_HALF_UP, Decimal

import numpy as np

# Maximum gap ratio before a window is considered invalid
MAX_GAP_RATIO = 0.10  # 10% null tolerance per window


def _to_decimal(value: float, places: int = 1) -> Decimal:
    """Round a float to the given decimal places and return as Decimal."""
    quantize_str = "0." + "0" * places
    return Decimal(str(value)).quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)


def best_effort(
    power_data: list[int | None],
    duration_seconds: int,
) -> tuple[Decimal, int] | None:
    """Find the best average power over a sliding window of given duration.

    Args:
        power_data: List of 1-second power samples (None for missing).
        duration_seconds: Window size in seconds.

    Returns:
        Tuple of (best_avg_power, start_index) or None if no valid window found.
        best_avg_power is a Decimal rounded to 1 decimal place.

    A window is valid if it has no more than MAX_GAP_RATIO (10%) null values.
    Nulls within a valid window are treated as 0W (coasting).
    """
    if not power_data or duration_seconds <= 0:
        return None

    n = len(power_data)
    if n < duration_seconds:
        return None

    # Build arrays: values (nulls -> 0) and valid mask (1 for non-null)
    values = np.zeros(n, dtype=np.float64)
    valid = np.zeros(n, dtype=np.float64)
    for i, p in enumerate(power_data):
        if p is not None:
            values[i] = float(p)
            valid[i] = 1.0

    # Sliding window sums using cumulative sums for O(n) performance
    cum_values = np.cumsum(values)
    cum_valid = np.cumsum(valid)

    # Prepend zero for easier window calculation
    cum_values = np.concatenate(([0.0], cum_values))
    cum_valid = np.concatenate(([0.0], cum_valid))

    # Window sums: for each starting index i, window is [i, i+duration_seconds)
    window_count = n - duration_seconds + 1
    window_sums = cum_values[duration_seconds:] - cum_values[:window_count]
    window_valid_counts = cum_valid[duration_seconds:] - cum_valid[:window_count]

    # Minimum valid samples per window
    min_valid = duration_seconds * (1.0 - MAX_GAP_RATIO)

    best_avg = -1.0
    best_idx = -1

    for i in range(window_count):
        if window_valid_counts[i] >= min_valid:
            avg = window_sums[i] / duration_seconds
            if avg > best_avg:
                best_avg = avg
                best_idx = i

    if best_idx < 0:
        return None

    return (_to_decimal(best_avg), best_idx)


def mean_max_power(
    power_data: list[int | None],
    durations: list[int],
) -> list[tuple[int, Decimal | None]]:
    """Compute best average power for each specified duration.

    Args:
        power_data: List of 1-second power samples.
        durations: List of durations in seconds to compute best efforts for.

    Returns:
        List of (duration, best_avg_power) tuples. best_avg_power is None
        if no valid window exists for that duration.
    """
    results: list[tuple[int, Decimal | None]] = []
    for dur in durations:
        effort = best_effort(power_data, dur)
        if effort is not None:
            results.append((dur, effort[0]))
        else:
            results.append((dur, None))
    return results
