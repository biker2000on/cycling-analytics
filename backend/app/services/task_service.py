"""Service for querying Celery task status."""

from celery.result import AsyncResult

from app.workers.celery_app import celery_app


def get_task_status(task_id: str) -> dict[str, object]:
    """Query Celery result backend for task status.

    Args:
        task_id: Celery task ID

    Returns:
        Dict with: task_id, status, progress, result, error, stage, detail
    """
    result = AsyncResult(task_id, app=celery_app)

    # Map Celery states to our response
    status = result.state
    progress = 0
    task_result = None
    error = None
    stage = None
    detail = None

    if status == "PENDING":
        progress = 0
    elif status == "STARTED":
        progress = 0
    elif status == "PROGRESS":
        meta = result.info if isinstance(result.info, dict) else {}
        progress = meta.get("current", 0)
        stage = meta.get("stage", None)
        detail = meta.get("detail", None)
    elif status == "SUCCESS":
        progress = 100
        task_result = result.result
    elif status == "FAILURE":
        progress = 0
        error = str(result.info) if result.info else "Unknown error"

    return {
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "result": task_result,
        "error": error,
        "stage": stage,
        "detail": detail,
    }
