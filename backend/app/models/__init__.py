"""ORM models — import all models so Alembic autogenerate can discover them."""

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.activity_lap import ActivityLap
from app.models.activity_stream import ActivityStream
from app.models.health_metric import HealthMetric, MetricType
from app.models.import_batch import ImportBatch, ImportBatchStatus
from app.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.models.user import User

__all__ = [
    "Activity",
    "ActivityLap",
    "ActivitySource",
    "ActivityStream",
    "HealthMetric",
    "ImportBatch",
    "ImportBatchStatus",
    "Integration",
    "IntegrationProvider",
    "IntegrationStatus",
    "MetricType",
    "ProcessingStatus",
    "User",
]
