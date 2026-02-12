"""Tests for Normalized Power calculation — Plan 2.1."""

from decimal import Decimal

import pytest

from app.utils.coggan_model import calculate_normalized_power


class TestNormalizedPowerSteadyRide:
    """Steady-state power should produce NP close to avg power."""

    def test_steady_200w_ride(self) -> None:
        """Constant 200W for 5 minutes: NP should be ~200W (within 1W)."""
        power_data = [200] * 300  # 5 minutes
        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        assert abs(result.np_watts - Decimal("200")) <= Decimal("1")
        assert result.avg_power == Decimal("200.0")
        assert result.confidence == "high"
        assert result.warnings == []

    def test_steady_150w_long_ride(self) -> None:
        """Constant 150W for 1 hour: NP should be ~150W."""
        power_data = [150] * 3600
        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        assert abs(result.np_watts - Decimal("150")) <= Decimal("1")


class TestNormalizedPowerVariable:
    """Variable power should produce NP > avg power."""

    def test_variable_power_np_greater_than_avg(self) -> None:
        """Alternating blocks of low/high power should give NP > avg power."""
        # 60s at 100W then 60s at 300W, repeated — creates variability
        # that the 30s rolling average cannot fully smooth out.
        power_data = ([100] * 60 + [300] * 60) * 3  # 6 minutes
        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        assert result.avg_power is not None
        assert result.np_watts > result.avg_power

    def test_highly_variable_power(self) -> None:
        """Sprint intervals should produce NP significantly > avg power."""
        # 30s at 400W + 30s at 100W, repeated 5 times
        power_data = ([400] * 30 + [100] * 30) * 5
        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        assert result.avg_power is not None
        # NP should be significantly higher than avg for interval work
        assert result.np_watts > result.avg_power + Decimal("20")


class TestNormalizedPowerEdgeCases:
    """Edge cases: short rides, nulls, zeros, spikes."""

    def test_short_ride_returns_avg_with_warning(self) -> None:
        """Fewer than 30 samples should return avg power with a warning."""
        power_data = [200] * 20  # 20 seconds
        result = calculate_normalized_power(power_data)

        assert result.np_watts == Decimal("200.0")
        assert result.avg_power == Decimal("200.0")
        assert any("shorter than 30s" in w for w in result.warnings)

    def test_empty_list_returns_none(self) -> None:
        """Empty power data should return None with 'insufficient'."""
        result = calculate_normalized_power([])

        assert result.np_watts is None
        assert result.avg_power is None
        assert result.confidence == "insufficient"

    def test_all_nulls_returns_none(self) -> None:
        """All None values should return None."""
        power_data: list[int | None] = [None] * 100
        result = calculate_normalized_power(power_data)

        assert result.np_watts is None
        assert result.avg_power is None
        assert result.confidence == "insufficient"
        assert any("null" in w.lower() for w in result.warnings)

    def test_zeros_included_as_coasting(self) -> None:
        """Zero values (coasting) should be included in calculation."""
        # 30s at 200W + 30s at 0W — avg is 100, but with zeros
        power_data = [200] * 60 + [0] * 60
        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        assert result.avg_power is not None
        # Avg should be 100
        assert abs(result.avg_power - Decimal("100")) <= Decimal("1")
        # NP should be higher than avg because of variability
        assert result.np_watts > result.avg_power

    def test_spike_handling(self) -> None:
        """Power spikes >2500W should be flagged but included."""
        power_data = [200] * 300
        power_data[50] = 3000  # spike
        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        assert any("2500W" in w for w in result.warnings)

    def test_low_coverage_flags_low_confidence(self) -> None:
        """< 50% non-null samples should flag as low confidence."""
        power_data: list[int | None] = [200] * 40 + [None] * 100
        result = calculate_normalized_power(power_data)

        assert result.confidence == "low"
        assert any("coverage" in w.lower() for w in result.warnings)

    def test_nulls_excluded_from_calculation(self) -> None:
        """Nulls should be stripped, not treated as zero."""
        # 60 valid samples at 200W with 10 nulls sprinkled in
        power_data: list[int | None] = [200] * 60
        for i in range(0, 60, 6):
            power_data[i] = None

        result = calculate_normalized_power(power_data)

        assert result.np_watts is not None
        # With nulls removed, we have 50 samples at 200W
        assert abs(result.np_watts - Decimal("200")) <= Decimal("1")

    def test_single_value_returns_avg(self) -> None:
        """Single sample: short ride path, returns that value."""
        result = calculate_normalized_power([250])

        assert result.np_watts == Decimal("250.0")
        assert result.avg_power == Decimal("250.0")
        assert any("shorter than 30s" in w for w in result.warnings)
