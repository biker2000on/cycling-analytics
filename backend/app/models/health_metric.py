"""HealthMetric ORM model — daily wellness data (sleep, weight, HRV, etc.)."""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MetricType(str, enum.Enum):
    sleep_score = "sleep_score"
    weight_kg = "weight_kg"
    resting_hr = "resting_hr"
    hrv_ms = "hrv_ms"
    body_battery = "body_battery"
    stress_avg = "stress_avg"


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_type: Mapped[MetricType] = mapped_column(
        Enum(MetricType, name="metric_type", native_enum=True), nullable=False
    )
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="health_metrics")  # noqa: F821

    def __repr__(self) -> str:
        return f"<HealthMetric id={self.id} type={self.metric_type} date={self.date}>"
