"""ActivityMetrics ORM model — computed Coggan metrics per activity."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityMetrics(Base):
    __tablename__ = "activity_metrics"
    __table_args__ = (
        UniqueConstraint("activity_id", "threshold_method", name="uq_activity_metrics_activity_method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Snapshot of FTP at computation time
    ftp_at_computation: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    # Computed metrics
    normalized_power: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tss: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    intensity_factor: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    zone_distribution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    variability_index: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    efficiency_factor: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Method used for threshold (manual, auto-detect, etc.)
    threshold_method: Mapped[str] = mapped_column(
        String(50), server_default="manual", nullable=False
    )

    # Timestamp
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    activity: Mapped["Activity"] = relationship(back_populates="metrics")  # noqa: F821
    user: Mapped["User"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ActivityMetrics activity_id={self.activity_id} "
            f"np={self.normalized_power} tss={self.tss}>"
        )
