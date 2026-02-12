"""Service for importing activities from CSV files."""

from datetime import datetime
from decimal import Decimal
from io import BytesIO

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.schemas.csv_import import CsvImportResponse, CsvRowError

logger = structlog.get_logger(__name__)


async def parse_and_import_csv(
    content: bytes,
    user_id: int,
    db: AsyncSession,
) -> CsvImportResponse:
    """Parse CSV content and import activities.

    Expected CSV columns:
    - date (required) - ISO format or similar parseable format
    - name (required) - activity name
    - sport_type (optional, default 'cycling')
    - duration_minutes (optional) - converted to seconds
    - distance_km (optional) - converted to meters
    - avg_power_watts (optional)
    - avg_hr (optional)
    - elevation_gain_m (optional) - converted to meters
    - notes (optional)

    Returns:
        CsvImportResponse with counts of imported, skipped, and errors.
    """
    imported = 0
    skipped = 0
    errors: list[CsvRowError] = []
    activity_ids: list[int] = []

    try:
        # Parse CSV with pandas
        df = pd.read_csv(BytesIO(content))
    except Exception as e:
        errors.append(CsvRowError(row=0, message=f"Failed to parse CSV: {e}"))
        return CsvImportResponse(
            imported=imported, skipped=skipped, errors=errors, activity_ids=activity_ids
        )

    # Check if CSV is empty
    if df.empty:
        errors.append(CsvRowError(row=0, message="CSV file is empty"))
        return CsvImportResponse(
            imported=imported, skipped=skipped, errors=errors, activity_ids=activity_ids
        )

    # Validate required columns
    required_columns = {"date", "name"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        errors.append(
            CsvRowError(
                row=0,
                message=f"Missing required columns: {', '.join(missing_columns)}",
            )
        )
        return CsvImportResponse(
            imported=imported, skipped=skipped, errors=errors, activity_ids=activity_ids
        )

    # Process each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 because pandas is 0-indexed and CSV has header row

        try:
            # Validate and parse date (required)
            if pd.isna(row.get("date")):
                errors.append(
                    CsvRowError(row=row_num, field="date", message="Date is required")
                )
                skipped += 1
                continue

            try:
                activity_date = pd.to_datetime(row["date"])
            except Exception as e:
                errors.append(
                    CsvRowError(
                        row=row_num, field="date", message=f"Invalid date format: {e}"
                    )
                )
                skipped += 1
                continue

            # Validate name (required)
            if pd.isna(row.get("name")) or not str(row["name"]).strip():
                errors.append(
                    CsvRowError(row=row_num, field="name", message="Name is required")
                )
                skipped += 1
                continue

            name = str(row["name"]).strip()

            # Extract optional fields with unit conversion
            sport_type = (
                str(row["sport_type"]).strip()
                if not pd.isna(row.get("sport_type"))
                else "cycling"
            )

            # Duration: convert minutes to seconds
            duration_seconds = None
            if not pd.isna(row.get("duration_minutes")):
                try:
                    duration_minutes = float(row["duration_minutes"])
                    if duration_minutes < 0:
                        errors.append(
                            CsvRowError(
                                row=row_num,
                                field="duration_minutes",
                                message="Duration cannot be negative",
                            )
                        )
                        skipped += 1
                        continue
                    duration_seconds = int(duration_minutes * 60)
                except (ValueError, TypeError) as e:
                    errors.append(
                        CsvRowError(
                            row=row_num,
                            field="duration_minutes",
                            message=f"Invalid duration: {e}",
                        )
                    )
                    skipped += 1
                    continue

            # Distance: convert km to meters
            distance_meters = None
            if not pd.isna(row.get("distance_km")):
                try:
                    distance_km = float(row["distance_km"])
                    if distance_km < 0:
                        errors.append(
                            CsvRowError(
                                row=row_num,
                                field="distance_km",
                                message="Distance cannot be negative",
                            )
                        )
                        skipped += 1
                        continue
                    distance_meters = Decimal(str(distance_km * 1000))
                except (ValueError, TypeError) as e:
                    errors.append(
                        CsvRowError(
                            row=row_num,
                            field="distance_km",
                            message=f"Invalid distance: {e}",
                        )
                    )
                    skipped += 1
                    continue

            # Elevation gain: convert m to meters (already in meters)
            elevation_gain_meters = None
            if not pd.isna(row.get("elevation_gain_m")):
                try:
                    elevation_gain = float(row["elevation_gain_m"])
                    if elevation_gain < 0:
                        errors.append(
                            CsvRowError(
                                row=row_num,
                                field="elevation_gain_m",
                                message="Elevation gain cannot be negative",
                            )
                        )
                        skipped += 1
                        continue
                    elevation_gain_meters = Decimal(str(elevation_gain))
                except (ValueError, TypeError) as e:
                    errors.append(
                        CsvRowError(
                            row=row_num,
                            field="elevation_gain_m",
                            message=f"Invalid elevation: {e}",
                        )
                    )
                    skipped += 1
                    continue

            # Power
            avg_power_watts = None
            if not pd.isna(row.get("avg_power_watts")):
                try:
                    power = float(row["avg_power_watts"])
                    if power < 0:
                        errors.append(
                            CsvRowError(
                                row=row_num,
                                field="avg_power_watts",
                                message="Power cannot be negative",
                            )
                        )
                        skipped += 1
                        continue
                    avg_power_watts = Decimal(str(power))
                except (ValueError, TypeError) as e:
                    errors.append(
                        CsvRowError(
                            row=row_num,
                            field="avg_power_watts",
                            message=f"Invalid power: {e}",
                        )
                    )
                    skipped += 1
                    continue

            # Heart rate
            avg_hr = None
            if not pd.isna(row.get("avg_hr")):
                try:
                    hr = int(float(row["avg_hr"]))
                    if hr < 0:
                        errors.append(
                            CsvRowError(
                                row=row_num,
                                field="avg_hr",
                                message="Heart rate cannot be negative",
                            )
                        )
                        skipped += 1
                        continue
                    avg_hr = hr
                except (ValueError, TypeError) as e:
                    errors.append(
                        CsvRowError(
                            row=row_num,
                            field="avg_hr",
                            message=f"Invalid heart rate: {e}",
                        )
                    )
                    skipped += 1
                    continue

            # Notes
            notes = (
                str(row["notes"]).strip() if not pd.isna(row.get("notes")) else None
            )

            # Validate at least duration or distance is present
            if duration_seconds is None and distance_meters is None:
                errors.append(
                    CsvRowError(
                        row=row_num,
                        message="At least one of duration_minutes or distance_km is required",
                    )
                )
                skipped += 1
                continue

            # Duplicate detection: same user + same date + same duration
            if duration_seconds is not None:
                stmt = select(Activity).where(
                    Activity.user_id == user_id,
                    Activity.activity_date == activity_date,
                    Activity.duration_seconds == duration_seconds,
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is not None:
                    errors.append(
                        CsvRowError(
                            row=row_num,
                            message=f"Duplicate activity detected (matches activity {existing.id})",
                        )
                    )
                    skipped += 1
                    continue

            # Create activity
            activity = Activity(
                user_id=user_id,
                source=ActivitySource.csv,
                activity_date=activity_date.to_pydatetime(),
                name=name,
                sport_type=sport_type,
                duration_seconds=duration_seconds,
                distance_meters=distance_meters,
                elevation_gain_meters=elevation_gain_meters,
                avg_power_watts=avg_power_watts,
                avg_hr=avg_hr,
                notes=notes,
                processing_status=ProcessingStatus.complete,
            )
            db.add(activity)
            await db.flush()

            activity_ids.append(activity.id)
            imported += 1

            logger.info(
                "csv_activity_imported",
                activity_id=activity.id,
                row=row_num,
                name=name,
            )

        except Exception as e:
            logger.exception("csv_row_import_failed", row=row_num, error=str(e))
            errors.append(
                CsvRowError(row=row_num, message=f"Unexpected error: {e}")
            )
            skipped += 1

    return CsvImportResponse(
        imported=imported,
        skipped=skipped,
        errors=errors,
        activity_ids=activity_ids,
    )
