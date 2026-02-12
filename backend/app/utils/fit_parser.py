"""FIT file parser — converts binary FIT files into structured Pydantic models.

Pure utility: no DB access, no Celery dependency.
Takes a file path, returns a FitParseResult with activity summary,
per-second stream data, lap records, and any parse warnings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import structlog

from app.schemas.fit_data import (
    ActivityData,
    FitParseResult,
    FitParseWarning,
    LapRecord,
    StreamRecord,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEMICIRCLE_TO_DEGREES: float = 180.0 / (2**31)
POWER_SPIKE_THRESHOLD: int = 2500


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_fit_file(file_path: str | Path) -> FitParseResult:
    """Parse a FIT file and return structured data.

    Args:
        file_path: Path to a .fit file on disk.

    Returns:
        FitParseResult with activity summary, streams, laps, and warnings.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid FIT file.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"FIT file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    warnings: list[FitParseWarning] = []

    try:
        import fitparse  # local import to keep module loadable without fitparse
    except ImportError:
        raise ImportError(
            "fitparse is required but not installed. "
            "Install it with: pip install fitparse"
        )

    try:
        fit_file = fitparse.FitFile(str(path))
        # Force parsing so errors surface immediately
        messages = list(fit_file.get_messages())
    except Exception as exc:
        raise ValueError(f"Failed to parse FIT file: {exc}") from exc

    # Collect messages by type
    session_msgs: list[Any] = []
    record_msgs: list[Any] = []
    lap_msgs: list[Any] = []
    device_info_msgs: list[Any] = []
    file_id_msgs: list[Any] = []

    for msg in messages:
        msg_type = msg.name
        if msg_type == "session":
            session_msgs.append(msg)
        elif msg_type == "record":
            record_msgs.append(msg)
        elif msg_type == "lap":
            lap_msgs.append(msg)
        elif msg_type == "device_info":
            device_info_msgs.append(msg)
        elif msg_type == "file_id":
            file_id_msgs.append(msg)

    # Build result
    activity = _extract_activity(session_msgs, device_info_msgs, file_id_msgs, warnings)
    streams = _extract_streams(record_msgs, activity.activity_date, warnings)
    laps = _extract_laps(lap_msgs, warnings)

    logger.info(
        "fit_parse_complete",
        file=str(path.name),
        records=len(streams),
        laps=len(laps),
        warnings=len(warnings),
    )

    return FitParseResult(
        activity=activity,
        streams=streams,
        laps=laps,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def semicircles_to_degrees(semicircles: int | float | None) -> Decimal | None:
    """Convert Garmin semicircle GPS coordinates to decimal degrees.

    Formula: degrees = semicircles * (180 / 2^31)
    """
    if semicircles is None:
        return None
    try:
        return Decimal(str(semicircles * SEMICIRCLE_TO_DEGREES))
    except (InvalidOperation, TypeError, OverflowError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def _safe_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        return None


def _get_field_value(message: Any, field_name: str) -> Any:
    """Extract a single field value from a fitparse message.

    Returns None if the field is not present.
    """
    try:
        field = message.get(field_name)
        if field is not None:
            # fitparse returns the raw value directly from get()
            return field
    except (AttributeError, KeyError):
        pass
    return None


def _get_field_value_by_data(message: Any, field_name: str) -> Any:
    """Extract a field value via get_values() dict — more robust for some messages."""
    try:
        values = message.get_values()
        return values.get(field_name)
    except (AttributeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Session / Activity extraction
# ---------------------------------------------------------------------------


def _extract_activity(
    session_msgs: list[Any],
    device_info_msgs: list[Any],
    file_id_msgs: list[Any],
    warnings: list[FitParseWarning],
) -> ActivityData:
    """Build ActivityData from session, device_info, and file_id messages."""
    data: dict[str, Any] = {}

    # Use the first session message (multi-sport files may have multiple)
    if session_msgs:
        session = session_msgs[0]
        vals = _msg_values(session)

        # Sport type
        sport = vals.get("sport")
        sub_sport = vals.get("sub_sport")
        if sport is not None:
            sport_str = str(sport)
            if sub_sport and str(sub_sport) != "generic":
                sport_str = f"{sport_str}/{sub_sport}"
            data["sport_type"] = sport_str

        # Timing
        start_time = vals.get("start_time") or vals.get("timestamp")
        if isinstance(start_time, datetime):
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=UTC)
            data["activity_date"] = start_time

        elapsed = vals.get("total_elapsed_time")
        if elapsed is not None:
            data["duration_seconds"] = _safe_int(elapsed)

        # Distance / elevation
        data["distance_meters"] = _safe_decimal(vals.get("total_distance"))
        data["elevation_gain_meters"] = _safe_decimal(vals.get("total_ascent"))

        # Power
        data["avg_power_watts"] = _safe_decimal(vals.get("avg_power"))
        data["max_power_watts"] = _safe_decimal(vals.get("max_power"))

        # Heart rate
        data["avg_hr"] = _safe_int(vals.get("avg_heart_rate"))
        data["max_hr"] = _safe_int(vals.get("max_heart_rate"))

        # Cadence
        data["avg_cadence"] = _safe_int(vals.get("avg_cadence"))

        # Calories
        data["calories"] = _safe_int(vals.get("total_calories"))
    else:
        warnings.append(
            FitParseWarning(message="No session message found in FIT file")
        )

    # Device name — try device_info first, fall back to file_id
    device_name = _extract_device_name(device_info_msgs, file_id_msgs)
    if device_name:
        data["device_name"] = device_name

    return ActivityData(**data)


def _extract_device_name(
    device_info_msgs: list[Any],
    file_id_msgs: list[Any],
) -> str | None:
    """Try to determine device name from device_info or file_id messages."""
    # Look at device_info messages for the main device (device_index == 0 or creator)
    for msg in device_info_msgs:
        vals = _msg_values(msg)
        device_index = vals.get("device_index")
        # device_index 0 is typically the recording device
        if device_index is not None and int(device_index) != 0:
            continue
        manufacturer = vals.get("manufacturer")
        product_name = vals.get("product_name") or vals.get("garmin_product")
        parts = [str(p) for p in [manufacturer, product_name] if p is not None]
        if parts:
            return " ".join(parts)

    # Fallback: file_id message
    for msg in file_id_msgs:
        vals = _msg_values(msg)
        manufacturer = vals.get("manufacturer")
        product_name = vals.get("product_name") or vals.get("garmin_product")
        parts = [str(p) for p in [manufacturer, product_name] if p is not None]
        if parts:
            return " ".join(parts)

    return None


# ---------------------------------------------------------------------------
# Record / stream extraction
# ---------------------------------------------------------------------------


def _extract_streams(
    record_msgs: list[Any],
    activity_start: datetime | None,
    warnings: list[FitParseWarning],
) -> list[StreamRecord]:
    """Build per-second StreamRecord list from record messages."""
    streams: list[StreamRecord] = []
    first_timestamp: datetime | None = None
    has_power_meter: bool | None = None  # Unknown until we see data

    for msg in record_msgs:
        vals = _msg_values(msg)

        # Timestamp is mandatory for a record
        ts = vals.get("timestamp")
        if ts is None:
            continue
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        if first_timestamp is None:
            first_timestamp = ts

        # Elapsed seconds from first record (or from activity start if available)
        elapsed: int | None = None
        if activity_start and isinstance(ts, datetime):
            delta = ts - activity_start
            elapsed = int(delta.total_seconds())
        elif first_timestamp and isinstance(ts, datetime):
            delta = ts - first_timestamp
            elapsed = int(delta.total_seconds())

        # Power — distinguish "no power meter" (None) vs "coasting" (0)
        raw_power = vals.get("power")
        power_watts: int | None = None
        if raw_power is not None:
            has_power_meter = True
            power_watts = _safe_int(raw_power)
            if power_watts is not None and power_watts > POWER_SPIKE_THRESHOLD:
                warnings.append(
                    FitParseWarning(
                        message=(
                            f"Power spike detected: {power_watts}W "
                            f"exceeds {POWER_SPIKE_THRESHOLD}W threshold"
                        ),
                        field="power",
                        value=str(power_watts),
                    )
                )
        elif has_power_meter is True:
            # We've seen power data before but this record has none — treat as 0 (coasting)
            power_watts = 0

        # GPS coordinates — prefer position_lat/long, convert from semicircles
        lat = semicircles_to_degrees(vals.get("position_lat"))
        lon = semicircles_to_degrees(vals.get("position_long"))

        # Speed — prefer enhanced_speed, fall back to speed
        speed_raw = vals.get("enhanced_speed") or vals.get("speed")
        speed_mps = _safe_decimal(speed_raw)

        # Altitude — prefer enhanced_altitude, fall back to altitude
        altitude_raw = vals.get("enhanced_altitude") or vals.get("altitude")
        altitude_meters = _safe_decimal(altitude_raw)

        record = StreamRecord(
            timestamp=ts,
            elapsed_seconds=elapsed,
            power_watts=power_watts,
            heart_rate=_safe_int(vals.get("heart_rate")),
            cadence=_safe_int(vals.get("cadence")),
            speed_mps=speed_mps,
            altitude_meters=altitude_meters,
            distance_meters=_safe_decimal(vals.get("distance")),
            temperature_c=_safe_decimal(vals.get("temperature")),
            latitude=lat,
            longitude=lon,
            grade_percent=_safe_decimal(vals.get("grade")),
        )
        streams.append(record)

    return streams


# ---------------------------------------------------------------------------
# Lap extraction
# ---------------------------------------------------------------------------


def _extract_laps(
    lap_msgs: list[Any],
    warnings: list[FitParseWarning],
) -> list[LapRecord]:
    """Build LapRecord list from lap messages."""
    laps: list[LapRecord] = []

    for idx, msg in enumerate(lap_msgs):
        vals = _msg_values(msg)

        start_time = vals.get("start_time") or vals.get("timestamp")
        if start_time is None:
            warnings.append(
                FitParseWarning(
                    message=f"Lap {idx} missing start_time, skipping",
                    field="start_time",
                )
            )
            continue

        if isinstance(start_time, datetime) and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)

        lap_trigger_raw = vals.get("lap_trigger")
        lap_trigger = str(lap_trigger_raw) if lap_trigger_raw is not None else None

        lap = LapRecord(
            lap_index=idx,
            start_time=start_time,
            total_elapsed_time=_safe_decimal(vals.get("total_elapsed_time")),
            total_distance=_safe_decimal(vals.get("total_distance")),
            avg_power=_safe_decimal(vals.get("avg_power")),
            max_power=_safe_decimal(vals.get("max_power")),
            avg_heart_rate=_safe_int(vals.get("avg_heart_rate")),
            max_heart_rate=_safe_int(vals.get("max_heart_rate")),
            avg_cadence=_safe_int(vals.get("avg_cadence")),
            lap_trigger=lap_trigger,
        )
        laps.append(lap)

    return laps


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _msg_values(message: Any) -> dict[str, Any]:
    """Extract all field values from a fitparse message as a dict.

    Uses get_values() which returns {field_name: value}.
    """
    try:
        return message.get_values()
    except (AttributeError, TypeError):
        return {}
