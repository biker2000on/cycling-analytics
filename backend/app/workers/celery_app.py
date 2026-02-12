"""Celery application configuration."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("cycling_analytics")
celery_app.conf.update(
    broker_url=settings.REDIS_URL,  # db0
    result_backend=settings.REDIS_URL.replace("/0", "/1"),  # db1
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_default_queue="high_priority",
    task_queues={
        "high_priority": {"exchange": "high_priority", "routing_key": "high_priority"},
        "low_priority": {"exchange": "low_priority", "routing_key": "low_priority"},
    },
    task_default_retry_delay=2,
    task_max_retries=3,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in app.workers.tasks package
celery_app.autodiscover_tasks(["app.workers.tasks"])
