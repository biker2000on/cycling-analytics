"""Test task for verifying Celery setup."""

import time

from app.workers.base_task import BaseTask
from app.workers.celery_app import celery_app


@celery_app.task(base=BaseTask, bind=True)
def test_task(self: BaseTask) -> dict[str, str]:
    """Simple test task that sleeps for 2 seconds."""
    time.sleep(2)
    return {"message": "test complete"}
