"""ActivityLap ORM model — lap splits from device or auto-lap.

Regular table (NOT a hypertable) because lap volume is low.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityLap(Base):
    __tablename__ = "activity_laps"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_elapsed_time: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    total_distance: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Power
    avg_power: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    max_power: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Heart rate
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cadence
    avg_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    activity: Mapped["Activity"] = relationship(back_populates="laps")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ActivityLap id={self.id} activity_id={self.activity_id} lap={self.lap_index}>"
