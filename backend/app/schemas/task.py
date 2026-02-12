"""Pydantic schemas for task status API."""

from pydantic import BaseModel, Field


class TaskStatusResponse(BaseModel):
    """Response model for task status endpoint."""

    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status (PENDING/STARTED/PROGRESS/SUCCESS/FAILURE/RETRY)")
    progress: int = Field(0, ge=0, le=100, description="Task progress percentage")
    result: dict[str, object] | None = Field(None, description="Task result if complete")
    error: str | None = Field(None, description="Error message if failed")
    stage: str | None = Field(None, description="Current processing stage")
    detail: str | None = Field(None, description="Additional detail about current progress")
