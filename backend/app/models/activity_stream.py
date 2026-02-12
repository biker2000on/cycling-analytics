"""ActivityStream ORM model — per-second time-series data.

This table becomes a TimescaleDB hypertable via the initial migration.
Composite PK: (activity_id, timestamp).
"""

from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityStream(Base):
    __tablename__ = "activity_streams"

    activity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Sensor data
    power_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speed_mps: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    altitude_meters: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    distance_meters: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # GPS position (POINT, WGS-84)
    position = mapped_column(
        Geography("POINT", srid=4326), nullable=True
    )

    grade_percent: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Relationship
    activity: Mapped["Activity"] = relationship(back_populates="streams")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ActivityStream activity_id={self.activity_id} ts={self.timestamp}>"
