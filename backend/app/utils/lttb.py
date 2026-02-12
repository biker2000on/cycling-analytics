"""Largest Triangle Three Buckets (LTTB) downsampling algorithm.

Reduces the number of points in a time series while preserving the visual
shape of the data.  Peaks, valleys, and inflection points are kept preferentially
over flat regions.

Reference: Sveinn Steinarsson, *Downsampling Time Series for Visual
Representation*, MSc thesis, University of Iceland, 2013.
"""

from decimal import Decimal


def lttb_downsample(data: list[tuple[float, float]], threshold: int) -> list[int]:
    """Return the indices of the points to keep after LTTB downsampling.

    Args:
        data: List of ``(x, y)`` tuples representing the time series.
              *x* is typically elapsed seconds, *y* the signal value.
        threshold: Target number of points in the output.  Must be >= 2.

    Returns:
        Sorted list of indices into *data* that should be retained.
        The first and last indices are always included.

    Raises:
        ValueError: If *threshold* < 2 or *data* has fewer than 2 points.
    """
    length = len(data)

    if threshold < 2:
        raise ValueError("threshold must be >= 2")

    if length < 2:
        raise ValueError("data must contain at least 2 points")

    # If we already have fewer (or equal) points than the threshold, keep all.
    if length <= threshold:
        return list(range(length))

    # Always keep first and last point.
    selected: list[int] = [0]

    # Number of buckets between the first and last fixed points.
    bucket_count = threshold - 2

    # Edge case: threshold == 2 means keep only first and last.
    if bucket_count == 0:
        selected.append(length - 1)
        return selected

    # Size of each bucket (float for even distribution).
    bucket_size = (length - 2) / bucket_count

    prev_selected_idx = 0

    for bucket_idx in range(bucket_count):
        # --- current bucket bounds ---
        bucket_start = int(1 + bucket_idx * bucket_size)
        bucket_end = int(1 + (bucket_idx + 1) * bucket_size)
        bucket_end = min(bucket_end, length - 1)  # clamp

        # --- next bucket average (used as the third triangle vertex) ---
        if bucket_idx < bucket_count - 1:
            next_start = int(1 + (bucket_idx + 1) * bucket_size)
            next_end = int(1 + (bucket_idx + 2) * bucket_size)
            next_end = min(next_end, length - 1)
        else:
            # Last bucket: the "next" point is the final data point.
            next_start = length - 1
            next_end = length

        avg_x = Decimal(0)
        avg_y = Decimal(0)
        next_count = next_end - next_start
        if next_count > 0:
            for j in range(next_start, next_end):
                avg_x += Decimal(str(data[j][0]))
                avg_y += Decimal(str(data[j][1]))
            avg_x /= Decimal(next_count)
            avg_y /= Decimal(next_count)

        # Previously selected point.
        prev_x = Decimal(str(data[prev_selected_idx][0]))
        prev_y = Decimal(str(data[prev_selected_idx][1]))

        # Find the point in the current bucket that maximises the triangle area
        # formed by (prev_selected, candidate, next_avg).
        best_area = Decimal(-1)
        best_idx = bucket_start

        for candidate in range(bucket_start, bucket_end):
            cx = Decimal(str(data[candidate][0]))
            cy = Decimal(str(data[candidate][1]))

            # Triangle area * 2 (we skip the /2 since we only compare).
            area = abs(
                (prev_x - avg_x) * (cy - prev_y)
                - (prev_x - cx) * (avg_y - prev_y)
            )
            if area > best_area:
                best_area = area
                best_idx = candidate

        selected.append(best_idx)
        prev_selected_idx = best_idx

    # Always keep last point.
    selected.append(length - 1)

    return selected
