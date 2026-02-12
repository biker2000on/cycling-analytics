"""Task status API endpoints."""

from fastapi import APIRouter

from app.schemas.task import TaskStatusResponse
from app.services.task_service import get_task_status

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_endpoint(task_id: str) -> dict[str, object]:
    """Get the status of a background task.

    Args:
        task_id: Celery task ID

    Returns:
        Task status response with current state and progress
    """
    return get_task_status(task_id)
