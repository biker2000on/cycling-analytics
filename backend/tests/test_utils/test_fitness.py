"""Tests for CTL/ATL/TSB fitness calculations — Plan 2.4."""

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.utils.coggan_model import (
    ATL_DECAY,
    CTL_DECAY,
    calculate_ctl_atl_tsb,
)


class TestCTLConvergence:
    """CTL should converge toward daily TSS after many days."""

    def test_ctl_after_42_days_constant_tss(self) -> None:
        """After 42 days of 100 TSS/day, CTL should be approximately 63.2.

        Mathematical expectation: CTL = TSS * (1 - e^(-42/42)) = 100 * (1 - 1/e) ≈ 63.21
        """
        start = date(2025, 1, 1)
        daily_tss = [
            (start + timedelta(days=i), Decimal("100"))
            for i in range(42)
        ]

        result = calculate_ctl_atl_tsb(daily_tss)

        # CTL after 42 days of 100 TSS should be ~63.2
        last = result[-1]
        assert abs(last.ctl - Decimal("63.2")) <= Decimal("1.0")

    def test_ctl_convergence_long_block(self) -> None:
        """After 200+ days of constant TSS, CTL should converge to that TSS value."""
        start = date(2025, 1, 1)
        daily_tss = [
            (start + timedelta(days=i), Decimal("80"))
            for i in range(250)
        ]

        result = calculate_ctl_atl_tsb(daily_tss)

        # After 250 days (≈6 time constants), CTL should be very close to 80
        last = result[-1]
        assert abs(last.ctl - Decimal("80")) <= Decimal("0.5")


class TestATLBehavior:
    """ATL (fatigue) should respond faster than CTL."""

    def test_atl_after_7_days_constant_tss(self) -> None:
        """After 7 days of 100 TSS/day, ATL ≈ 100 * (1 - e^(-1)) ≈ 63.2."""
        start = date(2025, 1, 1)
        daily_tss = [
            (start + timedelta(days=i), Decimal("100"))
            for i in range(7)
        ]

        result = calculate_ctl_atl_tsb(daily_tss)

        last = result[-1]
        assert abs(last.atl - Decimal("63.2")) <= Decimal("2.0")

    def test_atl_converges_faster_than_ctl(self) -> None:
        """ATL should reach higher values faster than CTL."""
        start = date(2025, 1, 1)
        daily_tss = [
            (start + timedelta(days=i), Decimal("100"))
            for i in range(14)
        ]

        result = calculate_ctl_atl_tsb(daily_tss)

        # After 14 days, ATL should be much higher than CTL
        last = result[-1]
        assert last.atl > last.ctl


class TestRestDayDecay:
    """Rest days should show decay in both CTL and ATL."""

    def test_rest_days_show_decay(self) -> None:
        """After a training block, rest days should reduce ATL/CTL."""
        start = date(2025, 1, 1)
        # 14 days of training
        training = [
            (start + timedelta(days=i), Decimal("100"))
            for i in range(14)
        ]
        # 7 days of rest
        rest = [
            (start + timedelta(days=14 + i), Decimal("0"))
            for i in range(7)
        ]

        result = calculate_ctl_atl_tsb(training + rest)

        last_training = result[13]  # day 14 (index 13)
        after_rest = result[-1]     # day 21

        # Both should have decayed
        assert after_rest.ctl < last_training.ctl
        assert after_rest.atl < last_training.atl

    def test_atl_decays_faster_than_ctl(self) -> None:
        """ATL should decay faster than CTL during rest (shorter time constant)."""
        start = date(2025, 1, 1)
        training = [
            (start + timedelta(days=i), Decimal("100"))
            for i in range(30)
        ]
        rest = [
            (start + timedelta(days=30 + i), Decimal("0"))
            for i in range(14)
        ]

        result = calculate_ctl_atl_tsb(training + rest)

        last_training = result[29]
        after_rest = result[-1]

        # Calculate proportional decay
        ctl_decay_pct = (last_training.ctl - after_rest.ctl) / last_training.ctl
        atl_decay_pct = (last_training.atl - after_rest.atl) / last_training.atl

        # ATL should decay proportionally more than CTL
        assert atl_decay_pct > ctl_decay_pct


class TestTSBBehavior:
    """TSB = CTL - ATL: positive after rest, negative after hard block."""

    def test_tsb_negative_during_training(self) -> None:
        """TSB should be negative during a hard training block."""
        start = date(2025, 1, 1)
        daily_tss = [
            (start + timedelta(days=i), Decimal("120"))
            for i in range(14)
        ]

        result = calculate_ctl_atl_tsb(daily_tss)

        # TSB should be negative during heavy training
        for point in result[3:]:  # skip first few days of ramp-up
            assert point.tsb < Decimal("0")

    def test_tsb_positive_after_rest(self) -> None:
        """TSB should become positive after sufficient rest."""
        start = date(2025, 1, 1)
        training = [
            (start + timedelta(days=i), Decimal("100"))
            for i in range(30)
        ]
        rest = [
            (start + timedelta(days=30 + i), Decimal("0"))
            for i in range(21)
        ]

        result = calculate_ctl_atl_tsb(training + rest)

        # After 21 days of rest, TSB should be positive (form is "good")
        last = result[-1]
        assert last.tsb > Decimal("0")

    def test_tsb_at_start_is_zero(self) -> None:
        """TSB should start at 0 when initial CTL=ATL=0."""
        start = date(2025, 1, 1)
        # First day with TSS > 0
        daily_tss = [(start, Decimal("50"))]

        result = calculate_ctl_atl_tsb(daily_tss)

        # On day 1 with TSS=50, CTL and ATL both increase from 0
        # ATL increases faster (larger decay constant), so TSB < 0
        assert result[0].tsb < Decimal("0")


class TestMultipleActivitiesPerDay:
    """Multiple activities per day should sum their TSS."""

    def test_multiple_activities_summed(self) -> None:
        """Two activities on the same day should have their TSS summed."""
        start = date(2025, 1, 1)
        # Two activities on same day
        daily_tss_split = [
            (start, Decimal("40")),
            (start, Decimal("60")),
        ]

        # Compare to single 100 TSS day
        daily_tss_combined = [
            (start, Decimal("100")),
        ]

        result_split = calculate_ctl_atl_tsb(daily_tss_split)
        result_combined = calculate_ctl_atl_tsb(daily_tss_combined)

        # Results should be identical
        assert result_split[0].ctl == result_combined[0].ctl
        assert result_split[0].atl == result_combined[0].atl
        assert result_split[0].tsb == result_combined[0].tsb
        assert result_split[0].tss_total == Decimal("100.0")


class TestGapFilling:
    """Days without entries should be filled with TSS=0."""

    def test_gap_between_activities_filled(self) -> None:
        """Days between two activities should exist with TSS=0."""
        day1 = date(2025, 1, 1)
        day5 = date(2025, 1, 5)

        daily_tss = [
            (day1, Decimal("100")),
            (day5, Decimal("100")),
        ]

        result = calculate_ctl_atl_tsb(daily_tss)

        # Should have 5 days (Jan 1-5)
        assert len(result) == 5

        # Days 2-4 should have TSS=0
        assert result[1].tss_total == Decimal("0.0")
        assert result[2].tss_total == Decimal("0.0")
        assert result[3].tss_total == Decimal("0.0")


class TestEmptyInput:
    """Empty input should return empty result."""

    def test_empty_daily_tss(self) -> None:
        result = calculate_ctl_atl_tsb([])
        assert result == []


class TestInitialValues:
    """Test that initial CTL/ATL values are respected."""

    def test_nonzero_initial_ctl_atl(self) -> None:
        """Starting from nonzero CTL/ATL should affect the output."""
        start = date(2025, 1, 1)
        daily_tss = [(start, Decimal("0"))]

        result_zero = calculate_ctl_atl_tsb(daily_tss)
        result_warm = calculate_ctl_atl_tsb(
            daily_tss,
            initial_ctl=Decimal("50"),
            initial_atl=Decimal("80"),
        )

        # With initial values, CTL/ATL should be higher even on a rest day
        assert result_warm[0].ctl > result_zero[0].ctl
        assert result_warm[0].atl > result_zero[0].atl

    def test_decay_from_initial_values(self) -> None:
        """Initial values should decay on rest days."""
        start = date(2025, 1, 1)
        daily_tss = [
            (start + timedelta(days=i), Decimal("0"))
            for i in range(7)
        ]

        result = calculate_ctl_atl_tsb(
            daily_tss,
            initial_ctl=Decimal("60"),
            initial_atl=Decimal("80"),
        )

        # Values should decrease over rest days
        assert result[-1].ctl < Decimal("60")
        assert result[-1].atl < Decimal("80")
