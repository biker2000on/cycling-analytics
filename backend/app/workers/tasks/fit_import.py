"""Celery task for processing uploaded FIT files.

Runs in Celery worker context with SYNC database access (psycopg2).
Parses the FIT file, updates the Activity record, and bulk-inserts
stream and lap records into the database.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func, insert, update

from app.config import get_settings
from app.models.activity import Activity, ProcessingStatus
from app.models.activity_lap import ActivityLap
from app.models.activity_stream import ActivityStream
from app.schemas.fit_data import FitParseResult, LapRecord, StreamRecord
from app.utils.fit_parser import parse_fit_file
from app.workers.base_task import BaseTask
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

STREAM_BATCH_SIZE = 1000


@celery_app.task(base=BaseTask, bind=True, name="app.workers.tasks.fit_import.process_fit_upload")
def process_fit_upload(self: BaseTask, activity_id: int, file_path: str) -> dict[str, Any]:
    """Parse an uploaded FIT file and store its data.

    Args:
        activity_id: Database ID of the Activity record.
        file_path: Relative path to the FIT file from FIT_STORAGE_PATH.

    Returns:
        Dict with activity_id, stream_count, and lap_count.
    """
    log = logger.bind(activity_id=activity_id, file_path=file_path)
    log.info("fit_import_started")

    session = self.session_maker()
    try:
        # 1. Update status to processing
        session.execute(
            update(Activity)
            .where(Activity.id == activity_id)
            .values(processing_status=ProcessingStatus.processing)
        )
        session.commit()

        # 2. Parse FIT file
        settings = get_settings()
        full_path = Path(settings.FIT_STORAGE_PATH) / file_path
        result: FitParseResult = parse_fit_file(full_path)

        log.info(
            "fit_parsed",
            streams=len(result.streams),
            laps=len(result.laps),
            warnings=len(result.warnings),
        )

        # 3. Update activity metadata from parsed session data
        activity_updates: dict[str, Any] = {
            "processing_status": ProcessingStatus.complete,
        }
        activity_data = result.activity

        if activity_data.sport_type is not None:
            activity_updates["sport_type"] = activity_data.sport_type
        if activity_data.activity_date is not None:
            activity_updates["activity_date"] = activity_data.activity_date
        if activity_data.name is not None:
            activity_updates["name"] = activity_data.name
        if activity_data.duration_seconds is not None:
            activity_updates["duration_seconds"] = activity_data.duration_seconds
        if activity_data.distance_meters is not None:
            activity_updates["distance_meters"] = activity_data.distance_meters
        if activity_data.elevation_gain_meters is not None:
            activity_updates["elevation_gain_meters"] = activity_data.elevation_gain_meters
        if activity_data.avg_power_watts is not None:
            activity_updates["avg_power_watts"] = activity_data.avg_power_watts
        if activity_data.max_power_watts is not None:
            activity_updates["max_power_watts"] = activity_data.max_power_watts
        if activity_data.avg_hr is not None:
            activity_updates["avg_hr"] = activity_data.avg_hr
        if activity_data.max_hr is not None:
            activity_updates["max_hr"] = activity_data.max_hr
        if activity_data.avg_cadence is not None:
            activity_updates["avg_cadence"] = activity_data.avg_cadence
        if activity_data.calories is not None:
            activity_updates["calories"] = activity_data.calories
        if activity_data.device_name is not None:
            activity_updates["device_name"] = activity_data.device_name

        # 4. Bulk insert stream records (batched)
        stream_count = _insert_streams(session, activity_id, result.streams, log)

        # 5. Insert lap records
        lap_count = _insert_laps(session, activity_id, result.laps, log)

        # 6. Update activity with parsed metadata
        session.execute(
            update(Activity)
            .where(Activity.id == activity_id)
            .values(**activity_updates)
        )
        session.commit()

        log.info(
            "fit_import_complete",
            stream_count=stream_count,
            lap_count=lap_count,
        )

        return {
            "activity_id": activity_id,
            "stream_count": stream_count,
            "lap_count": lap_count,
        }

    except Exception as exc:
        session.rollback()
        log.exception("fit_import_failed", error=str(exc))

        # Mark activity as errored
        try:
            session.execute(
                update(Activity)
                .where(Activity.id == activity_id)
                .values(
                    processing_status=ProcessingStatus.error,
                    error_message=str(exc)[:1000],
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            log.exception("failed_to_update_error_status")

        raise
    finally:
        session.close()


def _insert_streams(
    session: Any,
    activity_id: int,
    streams: list[StreamRecord],
    log: Any,
) -> int:
    """Bulk-insert stream records in batches of STREAM_BATCH_SIZE.

    GPS coordinates are stored as PostGIS GEOGRAPHY(POINT) using ST_GeogFromText.

    Returns:
        Number of stream records inserted.
    """
    if not streams:
        return 0

    total = len(streams)
    log.info("inserting_streams", total=total, batch_size=STREAM_BATCH_SIZE)

    for batch_start in range(0, total, STREAM_BATCH_SIZE):
        batch = streams[batch_start : batch_start + STREAM_BATCH_SIZE]
        rows = []
        for rec in batch:
            row: dict[str, Any] = {
                "activity_id": activity_id,
                "timestamp": rec.timestamp,
                "elapsed_seconds": rec.elapsed_seconds,
                "power_watts": rec.power_watts,
                "heart_rate": rec.heart_rate,
                "cadence": rec.cadence,
                "speed_mps": rec.speed_mps,
                "altitude_meters": rec.altitude_meters,
                "distance_meters": rec.distance_meters,
                "temperature_c": rec.temperature_c,
                "grade_percent": rec.grade_percent,
            }

            # Build PostGIS POINT for GPS data
            if rec.latitude is not None and rec.longitude is not None:
                row["position"] = func.ST_GeogFromText(
                    f"SRID=4326;POINT({rec.longitude} {rec.latitude})"
                )
            else:
                row["position"] = None

            rows.append(row)

        session.execute(insert(ActivityStream).values(rows))
        session.flush()

        log.debug(
            "stream_batch_inserted",
            batch_start=batch_start,
            batch_size=len(batch),
        )

    session.commit()
    return total


def _insert_laps(
    session: Any,
    activity_id: int,
    laps: list[LapRecord],
    log: Any,
) -> int:
    """Insert lap records into activity_laps.

    Returns:
        Number of lap records inserted.
    """
    if not laps:
        return 0

    rows = []
    for lap in laps:
        rows.append(
            {
                "activity_id": activity_id,
                "lap_index": lap.lap_index,
                "start_time": lap.start_time,
                "total_elapsed_time": lap.total_elapsed_time or Decimal("0"),
                "total_distance": lap.total_distance,
                "avg_power": lap.avg_power,
                "max_power": lap.max_power,
                "avg_heart_rate": lap.avg_heart_rate,
                "max_heart_rate": lap.max_heart_rate,
                "avg_cadence": lap.avg_cadence,
            }
        )

    session.execute(insert(ActivityLap).values(rows))
    session.commit()

    log.info("laps_inserted", count=len(rows))
    return len(rows)
