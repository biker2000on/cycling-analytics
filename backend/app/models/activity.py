"""Activity ORM model — one row per ride/run/workout."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivitySource(str, enum.Enum):
    fit_upload = "fit_upload"
    garmin = "garmin"
    strava = "strava"
    manual = "manual"
    csv = "csv"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    error = "error"


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[ActivitySource] = mapped_column(
        Enum(ActivitySource, name="activity_source", native_enum=True), nullable=False
    )
    activity_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    sport_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Duration / distance
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    elevation_gain_meters: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Power
    avg_power_watts: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    max_power_watts: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Heart rate
    avg_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cadence
    avg_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Calories
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Derived metrics (computed post-processing)
    tss: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    np_watts: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    intensity_factor: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # File / device
    fit_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status", native_enum=True),
        server_default="pending",
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="activities")  # noqa: F821
    streams: Mapped[list["ActivityStream"]] = relationship(  # noqa: F821
        back_populates="activity", lazy="selectin", cascade="all, delete-orphan"
    )
    laps: Mapped[list["ActivityLap"]] = relationship(  # noqa: F821
        back_populates="activity", lazy="selectin", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["ActivityMetrics"]] = relationship(  # noqa: F821
        back_populates="activity", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Activity id={self.id} name={self.name!r} date={self.activity_date}>"
