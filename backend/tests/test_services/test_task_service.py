"""Tests for task_service.get_task_status() — Plan 8.1.1."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.task_service import get_task_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_async_result(state: str, info: object = None, result: object = None):
    """Build a mock AsyncResult with the given state and info."""
    mock = MagicMock()
    mock.state = state
    mock.info = info
    mock.result = result
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("app.services.task_service.AsyncResult")
def test_pending_state(mock_ar_cls):
    """PENDING state returns progress=0, stage=None."""
    mock_ar_cls.return_value = _mock_async_result("PENDING")

    status = get_task_status("task-123")

    assert status["task_id"] == "task-123"
    assert status["status"] == "PENDING"
    assert status["progress"] == 0
    assert status["stage"] is None
    assert status["detail"] is None
    assert status["result"] is None
    assert status["error"] is None


@patch("app.services.task_service.AsyncResult")
def test_started_state(mock_ar_cls):
    """STARTED state returns progress=0, stage=None."""
    mock_ar_cls.return_value = _mock_async_result("STARTED")

    status = get_task_status("task-456")

    assert status["status"] == "STARTED"
    assert status["progress"] == 0
    assert status["stage"] is None
    assert status["detail"] is None


@patch("app.services.task_service.AsyncResult")
def test_progress_state(mock_ar_cls):
    """PROGRESS state returns actual progress and stage from meta."""
    meta = {"current": 42, "total": 100, "stage": "Inserting stream data 2/5"}
    mock_ar_cls.return_value = _mock_async_result("PROGRESS", info=meta)

    status = get_task_status("task-789")

    assert status["status"] == "PROGRESS"
    assert status["progress"] == 42
    assert status["stage"] == "Inserting stream data 2/5"
    assert status["detail"] is None


@patch("app.services.task_service.AsyncResult")
def test_progress_state_with_detail(mock_ar_cls):
    """PROGRESS state returns detail when present in meta."""
    meta = {
        "current": 75,
        "total": 100,
        "stage": "Analyzing laps",
        "detail": "Processing lap 3",
    }
    mock_ar_cls.return_value = _mock_async_result("PROGRESS", info=meta)

    status = get_task_status("task-detail")

    assert status["progress"] == 75
    assert status["stage"] == "Analyzing laps"
    assert status["detail"] == "Processing lap 3"


@patch("app.services.task_service.AsyncResult")
def test_progress_state_non_dict_info(mock_ar_cls):
    """PROGRESS state with non-dict info falls back gracefully."""
    mock_ar_cls.return_value = _mock_async_result("PROGRESS", info="unexpected")

    status = get_task_status("task-bad")

    assert status["status"] == "PROGRESS"
    assert status["progress"] == 0
    assert status["stage"] is None


@patch("app.services.task_service.AsyncResult")
def test_success_state(mock_ar_cls):
    """SUCCESS state returns progress=100, stage=None, and result."""
    task_result = {"activity_id": 1, "stream_count": 500, "lap_count": 5}
    mock_ar_cls.return_value = _mock_async_result(
        "SUCCESS", result=task_result
    )
    # AsyncResult.result is the return value for SUCCESS
    mock_ar_cls.return_value.result = task_result

    status = get_task_status("task-ok")

    assert status["status"] == "SUCCESS"
    assert status["progress"] == 100
    assert status["result"] == task_result
    assert status["stage"] is None
    assert status["error"] is None


@patch("app.services.task_service.AsyncResult")
def test_failure_state(mock_ar_cls):
    """FAILURE state returns progress=0 and error message."""
    exc_info = ValueError("Something went wrong")
    mock_ar_cls.return_value = _mock_async_result("FAILURE", info=exc_info)

    status = get_task_status("task-fail")

    assert status["status"] == "FAILURE"
    assert status["progress"] == 0
    assert status["error"] == "Something went wrong"
    assert status["result"] is None
    assert status["stage"] is None


@patch("app.services.task_service.AsyncResult")
def test_failure_state_no_info(mock_ar_cls):
    """FAILURE state with no info returns 'Unknown error'."""
    mock_ar_cls.return_value = _mock_async_result("FAILURE", info=None)

    status = get_task_status("task-fail-none")

    assert status["error"] == "Unknown error"
