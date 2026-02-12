"""ORM models — import all models so Alembic autogenerate can discover them."""

from app.models.activity import Activity, ActivitySource, ProcessingStatus
from app.models.activity_lap import ActivityLap
from app.models.activity_metrics import ActivityMetrics
from app.models.activity_stream import ActivityStream
from app.models.fitness_metrics import DailyFitness
from app.models.health_metric import HealthMetric, MetricType
from app.models.import_batch import ImportBatch, ImportBatchStatus
from app.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.models.threshold import Threshold, ThresholdMethod
from app.models.user import User
from app.models.user_settings import UserSettings

__all__ = [
    "Activity",
    "ActivityLap",
    "ActivityMetrics",
    "ActivitySource",
    "ActivityStream",
    "DailyFitness",
    "HealthMetric",
    "ImportBatch",
    "ImportBatchStatus",
    "Integration",
    "IntegrationProvider",
    "IntegrationStatus",
    "MetricType",
    "ProcessingStatus",
    "Threshold",
    "ThresholdMethod",
    "User",
    "UserSettings",
]
