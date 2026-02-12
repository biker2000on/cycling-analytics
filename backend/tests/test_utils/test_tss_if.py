"""Tests for TSS, IF, power zones, and zone distribution — Plan 2.2."""

from decimal import Decimal

import pytest

from app.utils.coggan_model import (
    calculate_intensity_factor,
    calculate_tss,
    calculate_zone_distribution,
    estimate_tss_from_avg_power,
    get_power_zone,
)


class TestIntensityFactor:
    """IF = NP / FTP."""

    def test_at_ftp(self) -> None:
        """NP == FTP should give IF = 1.000."""
        result = calculate_intensity_factor(Decimal("280"), Decimal("280"))
        assert result == Decimal("1.000")

    def test_below_ftp(self) -> None:
        """NP = 210 with FTP = 280 should give IF = 0.750."""
        result = calculate_intensity_factor(Decimal("210"), Decimal("280"))
        assert result == Decimal("0.750")

    def test_above_ftp(self) -> None:
        """NP = 336 with FTP = 280 should give IF = 1.200."""
        result = calculate_intensity_factor(Decimal("336"), Decimal("280"))
        assert result == Decimal("1.200")

    def test_zero_ftp_raises(self) -> None:
        """FTP = 0 should raise ValueError."""
        with pytest.raises(ValueError, match="FTP must be greater than zero"):
            calculate_intensity_factor(Decimal("200"), Decimal("0"))


class TestTSS:
    """TSS = (duration * NP * IF) / (FTP * 3600) * 100."""

    def test_one_hour_at_ftp(self) -> None:
        """1 hour at FTP: TSS = 100."""
        tss = calculate_tss(
            duration_seconds=3600,
            np_watts=Decimal("280"),
            if_value=Decimal("1.000"),
            ftp_watts=Decimal("280"),
        )
        assert tss == Decimal("100.0")

    def test_one_hour_at_75_percent(self) -> None:
        """1 hour at 75% FTP: TSS ~= 56.3."""
        ftp = Decimal("280")
        np_watts = Decimal("210")  # 75% of 280
        if_value = calculate_intensity_factor(np_watts, ftp)
        tss = calculate_tss(
            duration_seconds=3600,
            np_watts=np_watts,
            if_value=if_value,
            ftp_watts=ftp,
        )
        # TSS = (3600 * 210 * 0.75) / (280 * 3600) * 100 = 56.25
        assert abs(tss - Decimal("56.3")) <= Decimal("0.2")

    def test_half_hour_at_ftp(self) -> None:
        """30 min at FTP: TSS = 50."""
        tss = calculate_tss(
            duration_seconds=1800,
            np_watts=Decimal("280"),
            if_value=Decimal("1.000"),
            ftp_watts=Decimal("280"),
        )
        assert tss == Decimal("50.0")

    def test_zero_duration(self) -> None:
        """Zero duration should give TSS = 0."""
        tss = calculate_tss(
            duration_seconds=0,
            np_watts=Decimal("280"),
            if_value=Decimal("1.000"),
            ftp_watts=Decimal("280"),
        )
        assert tss == Decimal("0.0")

    def test_negative_duration_raises(self) -> None:
        """Negative duration should raise ValueError."""
        with pytest.raises(ValueError, match="Duration must be non-negative"):
            calculate_tss(
                duration_seconds=-100,
                np_watts=Decimal("200"),
                if_value=Decimal("1.000"),
                ftp_watts=Decimal("200"),
            )

    def test_zero_ftp_raises(self) -> None:
        """FTP = 0 should raise ValueError."""
        with pytest.raises(ValueError, match="FTP must be greater than zero"):
            calculate_tss(
                duration_seconds=3600,
                np_watts=Decimal("200"),
                if_value=Decimal("1.000"),
                ftp_watts=Decimal("0"),
            )


class TestEstimateTssFromAvgPower:
    """Manual entry TSS estimation using avg power."""

    def test_one_hour_at_ftp(self) -> None:
        """1 hour with avg_power == FTP should give TSS = 100."""
        tss = estimate_tss_from_avg_power(
            duration_seconds=3600,
            avg_power=Decimal("280"),
            ftp_watts=Decimal("280"),
        )
        assert tss == Decimal("100.0")

    def test_one_hour_below_ftp(self) -> None:
        """1 hour at 75% FTP: estimated TSS ~= 56.3."""
        tss = estimate_tss_from_avg_power(
            duration_seconds=3600,
            avg_power=Decimal("210"),
            ftp_watts=Decimal("280"),
        )
        assert abs(tss - Decimal("56.3")) <= Decimal("0.2")

    def test_zero_ftp_raises(self) -> None:
        """FTP = 0 should raise ValueError."""
        with pytest.raises(ValueError, match="FTP must be greater than zero"):
            estimate_tss_from_avg_power(
                duration_seconds=3600,
                avg_power=Decimal("200"),
                ftp_watts=Decimal("0"),
            )


class TestPowerZones:
    """Coggan power zone boundaries."""

    @pytest.mark.parametrize(
        ("power", "ftp", "expected_zone"),
        [
            (0, 200, 1),       # 0% → Z1
            (100, 200, 1),     # 50% → Z1 (< 55%)
            (109, 200, 1),     # 54.5% → Z1
            (110, 200, 2),     # 55% → Z2
            (150, 200, 2),     # 75% → Z2 (75% < 75% is false, 75% < 0.75 upper)
            (152, 200, 3),     # 76% → Z3
            (180, 200, 3),     # 90% → Z3 (90% < 90% upper)
            (182, 200, 4),     # 91% → Z4
            (210, 200, 4),     # 105% → Z4
            (212, 200, 5),     # 106% → Z5
            (240, 200, 5),     # 120% → Z5
            (242, 200, 6),     # 121% → Z6
            (300, 200, 6),     # 150% → Z6
            (302, 200, 7),     # 151% → Z7
            (500, 200, 7),     # 250% → Z7
        ],
    )
    def test_zone_boundaries(self, power: int, ftp: int, expected_zone: int) -> None:
        """Verify standard Coggan zone boundaries."""
        assert get_power_zone(power, ftp) == expected_zone

    def test_zero_ftp_raises(self) -> None:
        """FTP = 0 should raise ValueError."""
        with pytest.raises(ValueError, match="FTP must be greater than zero"):
            get_power_zone(200, 0)


class TestZoneDistribution:
    """Time-in-zone distribution calculations."""

    def test_all_in_one_zone(self) -> None:
        """All samples in Z2 (endurance)."""
        # 60% of 200 = 120W → Z2
        power_data = [120] * 100
        dist = calculate_zone_distribution(power_data, 200)

        assert dist.zone_seconds["z2"] == 100
        assert dist.total_seconds == 100
        # All others zero
        for z in ["z1", "z3", "z4", "z5", "z6", "z7"]:
            assert dist.zone_seconds[z] == 0

    def test_distribution_sums_to_total(self) -> None:
        """Sum of all zone seconds should equal total_seconds."""
        power_data = [50, 120, 170, 200, 220, 280, 400] * 10
        dist = calculate_zone_distribution(power_data, 200)

        zone_sum = sum(dist.zone_seconds.values())
        assert zone_sum == dist.total_seconds

    def test_nulls_excluded(self) -> None:
        """Null values should not be counted."""
        power_data: list[int | None] = [200] * 50 + [None] * 50
        dist = calculate_zone_distribution(power_data, 200)

        assert dist.total_seconds == 50

    def test_zeros_counted_in_z1(self) -> None:
        """Zeros (coasting) should be counted in Z1."""
        power_data = [0] * 60
        dist = calculate_zone_distribution(power_data, 200)

        assert dist.zone_seconds["z1"] == 60
        assert dist.total_seconds == 60

    def test_empty_data(self) -> None:
        """Empty data should produce all zeros."""
        dist = calculate_zone_distribution([], 200)

        assert dist.total_seconds == 0
        for z in ["z1", "z2", "z3", "z4", "z5", "z6", "z7"]:
            assert dist.zone_seconds[z] == 0
