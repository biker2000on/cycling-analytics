"""Tests for the LTTB (Largest Triangle Three Buckets) downsampling algorithm."""

import pytest

from app.utils.lttb import lttb_downsample


class TestLttbDownsample:
    """Unit tests for lttb_downsample()."""

    def test_simple_data(self) -> None:
        """Downsampling 10 points to 5 returns exactly 5 indices."""
        data = [(float(i), float(i * 2)) for i in range(10)]
        indices = lttb_downsample(data, 5)
        assert len(indices) == 5

    def test_preserves_first_and_last(self) -> None:
        """First and last points are always kept."""
        data = [(float(i), float(i)) for i in range(20)]
        indices = lttb_downsample(data, 5)
        assert indices[0] == 0
        assert indices[-1] == 19

    def test_threshold_ge_data_length_returns_all(self) -> None:
        """When threshold >= len(data), all indices are returned."""
        data = [(float(i), float(i)) for i in range(5)]

        # threshold == length
        indices = lttb_downsample(data, 5)
        assert indices == [0, 1, 2, 3, 4]

        # threshold > length
        indices = lttb_downsample(data, 10)
        assert indices == [0, 1, 2, 3, 4]

    def test_threshold_of_3(self) -> None:
        """Minimum meaningful threshold: first, one middle, last."""
        data = [(float(i), float(i ** 2)) for i in range(10)]
        indices = lttb_downsample(data, 3)
        assert len(indices) == 3
        assert indices[0] == 0
        assert indices[-1] == 9

    def test_threshold_of_2(self) -> None:
        """Threshold of 2 returns only first and last."""
        data = [(float(i), float(i)) for i in range(100)]
        indices = lttb_downsample(data, 2)
        assert indices == [0, 99]

    def test_preserves_peak(self) -> None:
        """A sharp peak in the data should be preserved by LTTB."""
        # Flat data with a single spike at index 5
        data = [(float(i), 0.0) for i in range(10)]
        data[5] = (5.0, 100.0)  # spike

        indices = lttb_downsample(data, 4)

        # The spike should be among the selected indices
        assert 5 in indices

    def test_sorted_output(self) -> None:
        """Returned indices are in ascending order."""
        data = [(float(i), float(i % 7)) for i in range(50)]
        indices = lttb_downsample(data, 10)
        assert indices == sorted(indices)

    def test_raises_on_threshold_less_than_2(self) -> None:
        """threshold < 2 raises ValueError."""
        data = [(0.0, 0.0), (1.0, 1.0)]
        with pytest.raises(ValueError, match="threshold must be >= 2"):
            lttb_downsample(data, 1)

    def test_raises_on_data_less_than_2(self) -> None:
        """Fewer than 2 data points raises ValueError."""
        with pytest.raises(ValueError, match="data must contain at least 2 points"):
            lttb_downsample([(0.0, 0.0)], 2)

    def test_no_duplicate_indices(self) -> None:
        """No index should appear more than once."""
        data = [(float(i), float(i * 3 - i ** 2)) for i in range(30)]
        indices = lttb_downsample(data, 8)
        assert len(indices) == len(set(indices))
