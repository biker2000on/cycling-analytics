"""Celery task for processing files within an import batch.

Wraps the existing FIT import logic and updates batch counters
on completion, failure, or skip.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import update

from app.models.import_batch import ImportBatch, ImportBatchStatus
from app.workers.base_task import BaseTask
from app.workers.celery_app import celery_app
from app.workers.tasks.fit_import import process_fit_upload

logger = structlog.get_logger(__name__)


def _update_batch_status(session: Any, batch_id: int) -> None:
    """Check if all files in the batch are done and update status accordingly."""
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        return

    total_done = batch.processed_files + batch.failed_files + batch.skipped_files
    if total_done >= batch.total_files:
        session.execute(
            update(ImportBatch)
            .where(ImportBatch.id == batch_id)
            .values(status=ImportBatchStatus.complete)
        )


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.workers.tasks.batch_import.process_batch_file",
    queue="low_priority",
)
def process_batch_file(
    self: BaseTask, batch_id: int, activity_id: int, file_path: str
) -> dict[str, Any]:
    """Process a single FIT file within a batch import.

    Delegates actual FIT parsing to process_fit_upload, then updates
    the ImportBatch counters.

    Args:
        batch_id: ID of the ImportBatch record.
        activity_id: Database ID of the Activity record.
        file_path: Relative path to the FIT file from FIT_STORAGE_PATH.

    Returns:
        Dict with batch_id, activity_id, and processing result.
    """
    log = logger.bind(batch_id=batch_id, activity_id=activity_id, file_path=file_path)
    log.info("batch_file_processing_started")

    session = self.session_maker()
    try:
        # Delegate to existing FIT import task (called as a regular function)
        result = process_fit_upload(activity_id, file_path)

        # Update batch counters: increment processed_files
        session.execute(
            update(ImportBatch)
            .where(ImportBatch.id == batch_id)
            .values(
                processed_files=ImportBatch.processed_files + 1,
            )
        )
        session.commit()

        # Refresh and check if batch is complete
        session.expire_all()
        _update_batch_status(session, batch_id)
        session.commit()

        log.info("batch_file_processing_complete", result=result)
        return {
            "batch_id": batch_id,
            "activity_id": activity_id,
            "status": "complete",
            "result": result,
        }

    except Exception as exc:
        session.rollback()
        log.exception("batch_file_processing_failed", error=str(exc))

        # Update batch counters: increment failed_files
        try:
            session.execute(
                update(ImportBatch)
                .where(ImportBatch.id == batch_id)
                .values(
                    failed_files=ImportBatch.failed_files + 1,
                )
            )
            session.commit()

            # Check if batch is complete
            session.expire_all()
            _update_batch_status(session, batch_id)
            session.commit()
        except Exception:
            session.rollback()
            log.exception("failed_to_update_batch_counters")

        raise
    finally:
        session.close()
