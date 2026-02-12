"""Tests for task status API."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_get_task_status_pending() -> None:
    """Test GET /tasks/{task_id} returns pending status."""
    mock_status = {
        "task_id": "test-task-123",
        "status": "PENDING",
        "progress": 0,
        "result": None,
        "error": None,
    }

    with patch("app.routers.tasks.get_task_status", return_value=mock_status):
        response = client.get("/tasks/test-task-123")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-123"
    assert data["status"] == "PENDING"
    assert data["progress"] == 0
    assert data["result"] is None
    assert data["error"] is None


@pytest.mark.asyncio
async def test_get_task_status_success() -> None:
    """Test GET /tasks/{task_id} returns success status with result."""
    mock_status = {
        "task_id": "test-task-456",
        "status": "SUCCESS",
        "progress": 100,
        "result": {"message": "test complete"},
        "error": None,
    }

    with patch("app.routers.tasks.get_task_status", return_value=mock_status):
        response = client.get("/tasks/test-task-456")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-456"
    assert data["status"] == "SUCCESS"
    assert data["progress"] == 100
    assert data["result"] == {"message": "test complete"}
    assert data["error"] is None


@pytest.mark.asyncio
async def test_get_task_status_failure() -> None:
    """Test GET /tasks/{task_id} returns failure status with error."""
    mock_status = {
        "task_id": "test-task-789",
        "status": "FAILURE",
        "progress": 0,
        "result": None,
        "error": "Task failed due to timeout",
    }

    with patch("app.routers.tasks.get_task_status", return_value=mock_status):
        response = client.get("/tasks/test-task-789")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-789"
    assert data["status"] == "FAILURE"
    assert data["progress"] == 0
    assert data["result"] is None
    assert data["error"] == "Task failed due to timeout"
