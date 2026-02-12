"""Unit tests for the FIT file parser.

Tests cover:
- Semicircle to degrees conversion
- Safe type conversion helpers
- Graceful handling of missing/malformed data
- Warning collection
- Error handling for non-FIT and missing files
- Full parse pipeline with mock FIT messages
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.fit_data import (
    ActivityData,
    FitParseResult,
    FitParseWarning,
    LapRecord,
    StreamRecord,
)
from app.utils.fit_parser import (
    SEMICIRCLE_TO_DEGREES,
    _extract_activity,
    _extract_laps,
    _extract_streams,
    _safe_decimal,
    _safe_int,
    parse_fit_file,
    semicircles_to_degrees,
)

# ---------------------------------------------------------------------------
# Semicircle conversion
# ---------------------------------------------------------------------------


class TestSemicirclesToDegrees:
    """Tests for the GPS semicircle-to-degrees conversion."""

    def test_zero_returns_zero(self) -> None:
        result = semicircles_to_degrees(0)
        assert result == Decimal("0.0")

    def test_positive_hemisphere(self) -> None:
        # Known value: 2**31 semicircles == 180 degrees (but that's the max)
        # 2**30 semicircles should be 90 degrees
        result = semicircles_to_degrees(2**30)
        assert result is not None
        assert abs(float(result) - 90.0) < 0.001

    def test_negative_hemisphere(self) -> None:
        result = semicircles_to_degrees(-(2**30))
        assert result is not None
        assert abs(float(result) - (-90.0)) < 0.001

    def test_none_returns_none(self) -> None:
        assert semicircles_to_degrees(None) is None

    def test_known_coordinate(self) -> None:
        """Test with a realistic coordinate value.

        Example: approximately 51.5074 (London latitude) in semicircles.
        51.5074 / (180 / 2^31) = ~614,413,124.7 semicircles
        """
        london_semicircles = int(51.5074 / SEMICIRCLE_TO_DEGREES)
        result = semicircles_to_degrees(london_semicircles)
        assert result is not None
        assert abs(float(result) - 51.5074) < 0.001

    def test_float_input(self) -> None:
        result = semicircles_to_degrees(614_413_124.7)
        assert result is not None
        assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# Safe type conversion helpers
# ---------------------------------------------------------------------------


class TestSafeInt:
    def test_valid_int(self) -> None:
        assert _safe_int(42) == 42

    def test_valid_float_truncates(self) -> None:
        assert _safe_int(3.7) == 3

    def test_valid_string_int(self) -> None:
        assert _safe_int("100") == 100

    def test_none_returns_none(self) -> None:
        assert _safe_int(None) is None

    def test_invalid_string_returns_none(self) -> None:
        assert _safe_int("not_a_number") is None

    def test_empty_string_returns_none(self) -> None:
        assert _safe_int("") is None


class TestSafeDecimal:
    def test_valid_int(self) -> None:
        result = _safe_decimal(42)
        assert result == Decimal("42")

    def test_valid_float(self) -> None:
        result = _safe_decimal(3.14)
        assert result is not None
        assert abs(float(result) - 3.14) < 0.001

    def test_none_returns_none(self) -> None:
        assert _safe_decimal(None) is None

    def test_invalid_returns_none(self) -> None:
        assert _safe_decimal("invalid") is None


# ---------------------------------------------------------------------------
# Mock FIT message helpers
# ---------------------------------------------------------------------------


def _make_message(name: str, values: dict[str, Any]) -> MagicMock:
    """Create a mock fitparse message with the given name and field values."""
    msg = MagicMock()
    msg.name = name
    msg.get_values.return_value = values

    def get_side_effect(field_name: str) -> Any:
        return values.get(field_name)

    msg.get.side_effect = get_side_effect
    return msg


# ---------------------------------------------------------------------------
# Activity extraction
# ---------------------------------------------------------------------------


class TestExtractActivity:
    def test_full_session(self) -> None:
        session = _make_message("session", {
            "sport": "cycling",
            "sub_sport": "road",
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "total_elapsed_time": 3600,
            "total_distance": 40000.5,
            "total_ascent": 650,
            "avg_power": 220,
            "max_power": 450,
            "avg_heart_rate": 155,
            "max_heart_rate": 185,
            "avg_cadence": 90,
            "total_calories": 1200,
        })
        device = _make_message("device_info", {
            "device_index": 0,
            "manufacturer": "garmin",
            "garmin_product": "edge_540",
        })

        warnings: list[FitParseWarning] = []
        result = _extract_activity([session], [device], [], warnings)

        assert isinstance(result, ActivityData)
        assert result.sport_type == "cycling/road"
        assert result.duration_seconds == 3600
        assert result.distance_meters == Decimal("40000.5")
        assert result.elevation_gain_meters == Decimal("650")
        assert result.avg_power_watts == Decimal("220")
        assert result.max_power_watts == Decimal("450")
        assert result.avg_hr == 155
        assert result.max_hr == 185
        assert result.avg_cadence == 90
        assert result.calories == 1200
        assert result.device_name == "garmin edge_540"
        assert result.activity_date == datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        assert len(warnings) == 0

    def test_no_session_warns(self) -> None:
        warnings: list[FitParseWarning] = []
        result = _extract_activity([], [], [], warnings)

        assert isinstance(result, ActivityData)
        assert result.sport_type is None
        assert len(warnings) == 1
        assert "No session message" in warnings[0].message

    def test_generic_sub_sport_excluded(self) -> None:
        session = _make_message("session", {
            "sport": "running",
            "sub_sport": "generic",
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
        })
        warnings: list[FitParseWarning] = []
        result = _extract_activity([session], [], [], warnings)

        assert result.sport_type == "running"

    def test_indoor_ride_no_distance(self) -> None:
        """Indoor rides may have no distance or GPS — parser should handle gracefully."""
        session = _make_message("session", {
            "sport": "cycling",
            "sub_sport": "indoor_cycling",
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "total_elapsed_time": 1800,
            "total_distance": None,
            "total_ascent": None,
            "avg_power": 200,
            "max_power": 380,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_activity([session], [], [], warnings)

        assert result.distance_meters is None
        assert result.elevation_gain_meters is None
        assert result.avg_power_watts == Decimal("200")

    def test_naive_timestamp_gets_utc(self) -> None:
        session = _make_message("session", {
            "start_time": datetime(2025, 7, 15, 8, 0, 0),  # naive
            "sport": "cycling",
        })
        warnings: list[FitParseWarning] = []
        result = _extract_activity([session], [], [], warnings)

        assert result.activity_date is not None
        assert result.activity_date.tzinfo == UTC

    def test_device_from_file_id_fallback(self) -> None:
        session = _make_message("session", {
            "sport": "cycling",
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
        })
        file_id = _make_message("file_id", {
            "manufacturer": "wahoo",
            "product_name": "elemnt_bolt",
        })
        warnings: list[FitParseWarning] = []
        result = _extract_activity([session], [], [file_id], warnings)

        assert result.device_name == "wahoo elemnt_bolt"


# ---------------------------------------------------------------------------
# Stream extraction
# ---------------------------------------------------------------------------


class TestExtractStreams:
    def test_full_record(self) -> None:
        ts = datetime(2025, 7, 15, 8, 0, 10, tzinfo=UTC)
        record = _make_message("record", {
            "timestamp": ts,
            "power": 250,
            "heart_rate": 160,
            "cadence": 92,
            "enhanced_speed": 8.5,
            "enhanced_altitude": 305.2,
            "distance": 85.0,
            "temperature": 22,
            "position_lat": int(51.5074 / SEMICIRCLE_TO_DEGREES),
            "position_long": int(-0.1278 / SEMICIRCLE_TO_DEGREES),
            "grade": 2.5,
        })

        activity_start = datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], activity_start, warnings)

        assert len(result) == 1
        rec = result[0]
        assert rec.timestamp == ts
        assert rec.elapsed_seconds == 10
        assert rec.power_watts == 250
        assert rec.heart_rate == 160
        assert rec.cadence == 92
        assert rec.speed_mps is not None
        assert abs(float(rec.speed_mps) - 8.5) < 0.01
        assert rec.altitude_meters is not None
        assert abs(float(rec.altitude_meters) - 305.2) < 0.1
        assert rec.latitude is not None
        assert abs(float(rec.latitude) - 51.5074) < 0.001
        assert rec.longitude is not None
        assert abs(float(rec.longitude) - (-0.1278)) < 0.001
        assert len(warnings) == 0

    def test_missing_power_no_meter(self) -> None:
        """When no power data at all, power should be None (no power meter)."""
        ts = datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        record = _make_message("record", {
            "timestamp": ts,
            "heart_rate": 140,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], None, warnings)

        assert len(result) == 1
        assert result[0].power_watts is None  # No power meter

    def test_zero_power_coasting(self) -> None:
        """After seeing power data, a record without power should be 0 (coasting)."""
        ts1 = datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        ts2 = datetime(2025, 7, 15, 8, 0, 1, tzinfo=UTC)

        record_with_power = _make_message("record", {
            "timestamp": ts1,
            "power": 200,
        })
        record_without_power = _make_message("record", {
            "timestamp": ts2,
            "heart_rate": 140,
        })

        warnings: list[FitParseWarning] = []
        result = _extract_streams([record_with_power, record_without_power], None, warnings)

        assert result[0].power_watts == 200
        assert result[1].power_watts == 0  # Coasting, not missing

    def test_power_spike_warning(self) -> None:
        ts = datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        record = _make_message("record", {
            "timestamp": ts,
            "power": 3000,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], None, warnings)

        assert result[0].power_watts == 3000  # Still stored
        assert len(warnings) == 1
        assert "spike" in warnings[0].message.lower()
        assert warnings[0].field == "power"

    def test_indoor_ride_no_gps(self) -> None:
        """Indoor rides have no GPS coordinates."""
        ts = datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        record = _make_message("record", {
            "timestamp": ts,
            "power": 200,
            "heart_rate": 145,
            "cadence": 88,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], None, warnings)

        assert result[0].latitude is None
        assert result[0].longitude is None
        assert result[0].speed_mps is None

    def test_skips_record_without_timestamp(self) -> None:
        record = _make_message("record", {"power": 200})
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], None, warnings)

        assert len(result) == 0

    def test_fallback_speed_and_altitude(self) -> None:
        """When enhanced_speed is absent, falls back to speed field."""
        ts = datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        record = _make_message("record", {
            "timestamp": ts,
            "speed": 7.0,
            "altitude": 200.5,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], None, warnings)

        assert result[0].speed_mps is not None
        assert abs(float(result[0].speed_mps) - 7.0) < 0.01
        assert result[0].altitude_meters is not None
        assert abs(float(result[0].altitude_meters) - 200.5) < 0.1

    def test_naive_timestamp_gets_utc(self) -> None:
        ts = datetime(2025, 7, 15, 8, 0, 0)  # naive
        record = _make_message("record", {"timestamp": ts, "heart_rate": 140})
        warnings: list[FitParseWarning] = []
        result = _extract_streams([record], None, warnings)

        assert result[0].timestamp.tzinfo == UTC


# ---------------------------------------------------------------------------
# Lap extraction
# ---------------------------------------------------------------------------


class TestExtractLaps:
    def test_full_lap(self) -> None:
        lap = _make_message("lap", {
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "total_elapsed_time": 600.0,
            "total_distance": 5000.0,
            "avg_power": 230,
            "max_power": 400,
            "avg_heart_rate": 160,
            "max_heart_rate": 175,
            "avg_cadence": 88,
            "lap_trigger": "distance",
        })
        warnings: list[FitParseWarning] = []
        result = _extract_laps([lap], warnings)

        assert len(result) == 1
        assert result[0].lap_index == 0
        assert result[0].total_elapsed_time == Decimal("600.0")
        assert result[0].total_distance == Decimal("5000.0")
        assert result[0].avg_power == Decimal("230")
        assert result[0].avg_heart_rate == 160
        assert result[0].lap_trigger == "distance"

    def test_lap_missing_start_time_warned(self) -> None:
        lap = _make_message("lap", {
            "total_elapsed_time": 300.0,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_laps([lap], warnings)

        assert len(result) == 0
        assert len(warnings) == 1
        assert "missing start_time" in warnings[0].message

    def test_multiple_laps_indexed(self) -> None:
        laps = [
            _make_message("lap", {
                "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
                "total_elapsed_time": 300.0,
            }),
            _make_message("lap", {
                "start_time": datetime(2025, 7, 15, 8, 5, 0, tzinfo=UTC),
                "total_elapsed_time": 310.0,
            }),
        ]
        warnings: list[FitParseWarning] = []
        result = _extract_laps(laps, warnings)

        assert len(result) == 2
        assert result[0].lap_index == 0
        assert result[1].lap_index == 1

    def test_lap_with_no_power(self) -> None:
        """Running laps often have no power data."""
        lap = _make_message("lap", {
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "total_elapsed_time": 600.0,
            "avg_heart_rate": 155,
        })
        warnings: list[FitParseWarning] = []
        result = _extract_laps([lap], warnings)

        assert result[0].avg_power is None
        assert result[0].avg_heart_rate == 155


# ---------------------------------------------------------------------------
# Full parse_fit_file integration tests (mocked fitparse)
# ---------------------------------------------------------------------------


class TestParseFitFileErrors:
    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="FIT file not found"):
            parse_fit_file("/nonexistent/path/file.fit")

    def test_not_a_file(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not a file"):
            parse_fit_file(tmp_path)

    def test_invalid_fit_file(self, tmp_path: Path) -> None:
        """A file with non-FIT content should raise ValueError."""
        bad_file = tmp_path / "bad.fit"
        bad_file.write_text("this is not a FIT file")

        with pytest.raises(ValueError, match="Failed to parse"):
            parse_fit_file(bad_file)


class TestParseFitFileMocked:
    """Integration test with mocked fitparse.FitFile."""

    def test_full_pipeline(self, tmp_path: Path) -> None:
        """Simulate a complete FIT file parse with session, records, and laps."""
        fit_file = tmp_path / "test.fit"
        fit_file.write_bytes(b"\x00" * 10)  # Dummy content

        session = _make_message("session", {
            "sport": "cycling",
            "sub_sport": "generic",
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "total_elapsed_time": 1800,
            "total_distance": 20000,
            "avg_power": 210,
            "max_power": 400,
            "avg_heart_rate": 150,
            "max_heart_rate": 180,
            "avg_cadence": 85,
            "total_calories": 800,
            "total_ascent": 300,
        })
        record1 = _make_message("record", {
            "timestamp": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "power": 210,
            "heart_rate": 150,
            "cadence": 85,
            "enhanced_speed": 8.0,
            "enhanced_altitude": 100.0,
            "distance": 0.0,
        })
        record2 = _make_message("record", {
            "timestamp": datetime(2025, 7, 15, 8, 0, 1, tzinfo=UTC),
            "power": 220,
            "heart_rate": 152,
            "cadence": 86,
            "enhanced_speed": 8.2,
            "enhanced_altitude": 100.1,
            "distance": 8.0,
        })
        lap = _make_message("lap", {
            "start_time": datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
            "total_elapsed_time": 1800,
            "total_distance": 20000,
            "avg_power": 210,
            "avg_heart_rate": 150,
            "lap_trigger": "session_end",
        })
        device = _make_message("device_info", {
            "device_index": 0,
            "manufacturer": "garmin",
            "garmin_product": "edge_840",
        })

        mock_fit = MagicMock()
        mock_fit.get_messages.return_value = [session, record1, record2, lap, device]

        with patch("fitparse.FitFile", return_value=mock_fit):
            result = parse_fit_file(fit_file)

        assert isinstance(result, FitParseResult)

        # Activity
        assert result.activity.sport_type == "cycling"
        assert result.activity.duration_seconds == 1800
        assert result.activity.avg_power_watts == Decimal("210")
        assert result.activity.device_name == "garmin edge_840"

        # Streams
        assert len(result.streams) == 2
        assert result.streams[0].power_watts == 210
        assert result.streams[1].power_watts == 220

        # Laps
        assert len(result.laps) == 1
        assert result.laps[0].lap_trigger == "session_end"

        # Warnings
        assert len(result.warnings) == 0

    def test_empty_fit_file(self, tmp_path: Path) -> None:
        """A FIT file with no session/record/lap messages still returns partial result."""
        fit_file = tmp_path / "empty.fit"
        fit_file.write_bytes(b"\x00" * 10)

        # Only unknown message types
        unknown_msg = _make_message("unknown_msg_type", {"field": "value"})
        mock_fit = MagicMock()
        mock_fit.get_messages.return_value = [unknown_msg]

        with patch("fitparse.FitFile", return_value=mock_fit):
            result = parse_fit_file(fit_file)

        assert isinstance(result, FitParseResult)
        assert result.activity.sport_type is None
        assert len(result.streams) == 0
        assert len(result.laps) == 0
        # Should warn about missing session
        assert any("No session message" in w.message for w in result.warnings)


# ---------------------------------------------------------------------------
# Pydantic schema tests
# ---------------------------------------------------------------------------


class TestSchemaModels:
    """Verify Pydantic models serialize/deserialize correctly."""

    def test_stream_record_all_none(self) -> None:
        """StreamRecord with only timestamp should work fine."""
        record = StreamRecord(
            timestamp=datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC)
        )
        assert record.power_watts is None
        assert record.latitude is None

    def test_fit_parse_result_roundtrip(self) -> None:
        """FitParseResult should round-trip through JSON."""
        result = FitParseResult(
            activity=ActivityData(
                sport_type="cycling",
                duration_seconds=3600,
                avg_power_watts=Decimal("220.5"),
            ),
            streams=[
                StreamRecord(
                    timestamp=datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
                    power_watts=220,
                    heart_rate=155,
                )
            ],
            laps=[
                LapRecord(
                    lap_index=0,
                    start_time=datetime(2025, 7, 15, 8, 0, 0, tzinfo=UTC),
                    total_elapsed_time=Decimal("3600.0"),
                )
            ],
            warnings=[
                FitParseWarning(message="test warning", field="power", value="3000")
            ],
        )

        json_str = result.model_dump_json()
        restored = FitParseResult.model_validate_json(json_str)

        assert restored.activity.sport_type == "cycling"
        assert len(restored.streams) == 1
        assert restored.streams[0].power_watts == 220
        assert len(restored.laps) == 1
        assert len(restored.warnings) == 1

    def test_activity_data_defaults(self) -> None:
        """ActivityData with no arguments should have all None fields."""
        activity = ActivityData()
        assert activity.sport_type is None
        assert activity.duration_seconds is None
        assert activity.avg_power_watts is None
