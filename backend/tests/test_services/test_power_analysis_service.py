"""Tests for power analysis service (Phase 7)."""

from decimal import Decimal

import pytest

from app.services.power_analysis_service import (
    compute_hr_distribution,
    compute_hr_time_in_zones,
    compute_peak_efforts,
    compute_power_distribution,
    compute_power_stats,
    compute_zone_blocks,
)


class TestComputeZoneBlocks:
    """Tests for 30-second zone block computation."""

    def test_single_block_z2(self) -> None:
        """Power at 65% FTP should be Z2."""
        ftp = 200
        # 30 seconds at 130W (65% of 200 = Z2)
        power = [130] * 30
        blocks = compute_zone_blocks(power, ftp)
        assert len(blocks) == 1
        assert blocks[0].zone == 2
        assert blocks[0].start_seconds == 0
        assert blocks[0].end_seconds == 30

    def test_multiple_blocks(self) -> None:
        """Multiple 30-second blocks at different intensities."""
        ftp = 200
        power = [100] * 30 + [220] * 30  # Z1 + Z5
        blocks = compute_zone_blocks(power, ftp)
        assert len(blocks) == 2
        assert blocks[0].zone == 1  # 100/200 = 50% -> Z1
        assert blocks[1].zone == 5  # 220/200 = 110% -> Z5

    def test_partial_last_block(self) -> None:
        """A block shorter than 30 seconds at the end."""
        ftp = 200
        power = [200] * 45  # 1.5 blocks
        blocks = compute_zone_blocks(power, ftp)
        assert len(blocks) == 2

    def test_all_null_block(self) -> None:
        """Block with all null values should be Z1 with 0 power."""
        ftp = 200
        power: list[int | None] = [None] * 30
        blocks = compute_zone_blocks(power, ftp)
        assert len(blocks) == 1
        assert blocks[0].zone == 1
        assert blocks[0].avg_power == Decimal("0")

    def test_mixed_null_block(self) -> None:
        """Block with some nulls uses average of valid values."""
        ftp = 200
        power: list[int | None] = [300] * 15 + [None] * 15
        blocks = compute_zone_blocks(power, ftp)
        assert len(blocks) == 1
        assert blocks[0].avg_power == Decimal("300.0")
        # 300/200 = 1.50 which is < 1.51 (Z6 upper), so it's Z6
        assert blocks[0].zone == 6

    def test_empty_power_data(self) -> None:
        """Empty power data returns no blocks."""
        blocks = compute_zone_blocks([], 200)
        assert blocks == []


class TestComputePowerDistribution:
    """Tests for power distribution histogram."""

    def test_basic_distribution(self) -> None:
        """Power values should be binned into 10W bins."""
        ftp = 200
        power: list[int | None] = [105, 110, 115, 205, 210]
        dist = compute_power_distribution(power, ftp)
        assert len(dist) >= 2

        # Check bins exist for the 100-110 range and 200-210 range
        bins_starts = {b.bin_start for b in dist}
        assert 100 in bins_starts
        assert 110 in bins_starts
        assert 200 in bins_starts
        assert 210 in bins_starts

    def test_empty_data(self) -> None:
        """Empty data returns empty distribution."""
        assert compute_power_distribution([], 200) == []

    def test_all_nulls(self) -> None:
        """All null data returns empty distribution."""
        assert compute_power_distribution([None, None], 200) == []

    def test_zone_assignment(self) -> None:
        """Each bin should have a zone assigned based on mid-point."""
        ftp = 200
        power: list[int | None] = [50] * 10  # Z1 range
        dist = compute_power_distribution(power, ftp)
        assert len(dist) == 1
        assert dist[0].zone == 1


class TestComputePeakEfforts:
    """Tests for peak effort computation."""

    def test_basic_peaks(self) -> None:
        """Should return peak efforts for durations within data length."""
        power: list[int | None] = [200] * 400  # 400 seconds
        peaks = compute_peak_efforts(power)

        # 5s and 30s and 1min and 5min should have values
        five_sec = next(p for p in peaks if p.duration_seconds == 5)
        assert five_sec.power_watts is not None
        assert float(five_sec.power_watts) == pytest.approx(200, abs=1)

        five_min = next(p for p in peaks if p.duration_seconds == 300)
        assert five_min.power_watts is not None

    def test_durations_exceeding_data(self) -> None:
        """Durations longer than data should return None."""
        power: list[int | None] = [200] * 10  # Only 10 seconds
        peaks = compute_peak_efforts(power)

        five_sec = next(p for p in peaks if p.duration_seconds == 5)
        assert five_sec.power_watts is not None

        five_min = next(p for p in peaks if p.duration_seconds == 300)
        assert five_min.power_watts is None

    def test_wpkg_calculation(self) -> None:
        """W/kg should be calculated when weight is provided."""
        power: list[int | None] = [200] * 10
        peaks = compute_peak_efforts(power, weight_kg=75.0)

        five_sec = next(p for p in peaks if p.duration_seconds == 5)
        assert five_sec.power_wpkg is not None
        assert float(five_sec.power_wpkg) == pytest.approx(200.0 / 75.0, abs=0.1)


class TestComputePowerStats:
    """Tests for advanced power statistics."""

    def test_basic_stats(self) -> None:
        """Should compute NP, avg, max, VI, IF, TSS, work."""
        power: list[int | None] = [200] * 3600  # 1 hour at 200W
        stats = compute_power_stats(power, ftp=200, duration_seconds=3600)

        assert stats.avg_power is not None
        assert float(stats.avg_power) == pytest.approx(200, abs=1)
        assert stats.max_power == 200
        assert stats.normalized_power is not None
        assert stats.variability_index is not None
        assert stats.intensity_factor is not None
        assert stats.tss is not None
        assert stats.work_kj is not None

    def test_empty_data(self) -> None:
        """Empty power data returns empty stats."""
        stats = compute_power_stats([], ftp=200)
        assert stats.avg_power is None
        assert stats.max_power is None

    def test_with_weight(self) -> None:
        """W/kg is computed when weight is provided."""
        power: list[int | None] = [200] * 100
        stats = compute_power_stats(power, ftp=200, weight_kg=75.0)
        assert stats.watts_per_kg is not None
        assert float(stats.watts_per_kg) == pytest.approx(200.0 / 75.0, abs=0.1)


class TestComputeHRDistribution:
    """Tests for HR distribution histogram."""

    def test_basic_distribution(self) -> None:
        """HR values should be binned into 5 bpm bins."""
        hr: list[int | None] = [140, 142, 145, 150, 155]
        dist = compute_hr_distribution(hr)
        assert len(dist) >= 2

    def test_empty_data(self) -> None:
        """Empty data returns empty distribution."""
        assert compute_hr_distribution([]) == []

    def test_all_nulls(self) -> None:
        """All null data returns empty distribution."""
        assert compute_hr_distribution([None, None]) == []


class TestComputeHRTimeInZones:
    """Tests for HR time-in-zone computation."""

    def test_basic_zones(self) -> None:
        """HR values should be classified into 5 zones."""
        max_hr = 200
        # Z1 < 136, Z2 136-164, Z3 164-174, Z4 174-184, Z5 > 184
        hr: list[int | None] = [100] * 10 + [150] * 10 + [170] * 10 + [180] * 10 + [195] * 10
        zones = compute_hr_time_in_zones(hr, max_hr)

        assert len(zones) == 5
        assert zones[0].zone == 1
        assert zones[0].seconds == 10
        assert zones[1].zone == 2
        assert zones[1].seconds == 10

    def test_all_nulls(self) -> None:
        """All null data means zero seconds in all zones."""
        zones = compute_hr_time_in_zones([None, None], 190)
        assert all(z.seconds == 0 for z in zones)
