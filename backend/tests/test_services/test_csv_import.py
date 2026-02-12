"""Tests for CSV import service."""

from decimal import Decimal
from io import StringIO
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.csv_import_service import parse_and_import_csv


@pytest.mark.asyncio
async def test_parse_valid_csv_imports_all_rows() -> None:
    """Import a valid CSV with multiple rows should succeed."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km,avg_power_watts,avg_hr,elevation_gain_m,notes
2024-06-15,Morning Ride,cycling,90,45.2,210,145,520,Great weather
2024-06-14,Recovery Spin,cycling,45,20.1,150,125,100,Easy day
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # No duplicates
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock flush to set activity IDs
    activity_counter = [0]

    async def mock_flush() -> None:
        activity_counter[0] += 1
        # Set ID on the last added activity
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = activity_counter[0]

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 2
    assert result.skipped == 0
    assert len(result.errors) == 0
    assert len(result.activity_ids) == 2
    assert mock_db.add.call_count == 2


@pytest.mark.asyncio
async def test_parse_csv_with_missing_date_skips_row() -> None:
    """CSV row with missing date should be skipped with error."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
,Morning Ride,cycling,90,45.2
2024-06-14,Recovery Spin,cycling,45,20.1
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert result.errors[0].field == "date"
    assert result.errors[0].row == 2


@pytest.mark.asyncio
async def test_parse_csv_with_missing_name_skips_row() -> None:
    """CSV row with missing name should be skipped with error."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
2024-06-15,,cycling,90,45.2
2024-06-14,Recovery Spin,cycling,45,20.1
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert result.errors[0].field == "name"
    assert result.errors[0].row == 2


@pytest.mark.asyncio
async def test_parse_csv_with_negative_duration_skips_row() -> None:
    """CSV row with negative duration should be skipped with error."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
2024-06-15,Bad Ride,cycling,-90,45.2
2024-06-14,Recovery Spin,cycling,45,20.1
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert result.errors[0].field == "duration_minutes"
    assert "negative" in result.errors[0].message.lower()


@pytest.mark.asyncio
async def test_parse_csv_with_negative_distance_skips_row() -> None:
    """CSV row with negative distance should be skipped with error."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
2024-06-15,Bad Ride,cycling,90,-45.2
2024-06-14,Recovery Spin,cycling,45,20.1
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert result.errors[0].field == "distance_km"
    assert "negative" in result.errors[0].message.lower()


@pytest.mark.asyncio
async def test_parse_csv_detects_duplicates() -> None:
    """CSV row matching existing activity should be skipped as duplicate."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
2024-06-15,Morning Ride,cycling,90,45.2
"""
    # Mock existing activity
    from types import SimpleNamespace

    existing_activity = SimpleNamespace(id=42)

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_activity  # Duplicate found
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 0
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert "Duplicate" in result.errors[0].message
    assert "42" in result.errors[0].message


@pytest.mark.asyncio
async def test_parse_csv_converts_units() -> None:
    """CSV should convert units: km->meters, minutes->seconds."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km,elevation_gain_m
2024-06-15,Morning Ride,cycling,90,45.2,520
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1

    # Check the activity that was added
    added_activity = mock_db.add.call_args[0][0]
    assert added_activity.duration_seconds == 5400  # 90 minutes = 5400 seconds
    assert added_activity.distance_meters == Decimal("45200")  # 45.2 km = 45200 meters
    assert added_activity.elevation_gain_meters == Decimal("520")  # already in meters


@pytest.mark.asyncio
async def test_parse_csv_requires_duration_or_distance() -> None:
    """CSV row with neither duration nor distance should be skipped."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km,avg_power_watts
2024-06-15,Bad Ride,cycling,,,200
2024-06-14,Good Ride,cycling,45,20,200
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1
    assert result.skipped == 1
    assert len(result.errors) == 1
    assert "duration" in result.errors[0].message.lower() or "distance" in result.errors[0].message.lower()


@pytest.mark.asyncio
async def test_parse_empty_csv_returns_error() -> None:
    """Empty CSV (just headers or no content) should return error."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
"""
    mock_db = AsyncMock()

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 0
    assert result.skipped == 0
    assert len(result.errors) == 1
    assert "empty" in result.errors[0].message.lower()


@pytest.mark.asyncio
async def test_parse_csv_with_missing_columns_returns_error() -> None:
    """CSV missing required columns should return error."""
    csv_content = """name,sport_type,duration_minutes
Morning Ride,cycling,90
"""
    mock_db = AsyncMock()

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 0
    assert len(result.errors) == 1
    assert "Missing required columns" in result.errors[0].message
    assert "date" in result.errors[0].message


@pytest.mark.asyncio
async def test_parse_csv_sets_source_and_status() -> None:
    """Imported activities should have source=csv and status=complete."""
    csv_content = """date,name,sport_type,duration_minutes,distance_km
2024-06-15,Morning Ride,cycling,90,45.2
"""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_flush() -> None:
        if mock_db.add.call_count > 0:
            activity = mock_db.add.call_args[0][0]
            activity.id = mock_db.add.call_count

    mock_db.flush = AsyncMock(side_effect=mock_flush)

    result = await parse_and_import_csv(csv_content.encode("utf-8"), user_id=1, db=mock_db)

    assert result.imported == 1

    added_activity = mock_db.add.call_args[0][0]
    from app.models.activity import ActivitySource, ProcessingStatus

    assert added_activity.source == ActivitySource.csv
    assert added_activity.processing_status == ProcessingStatus.complete
