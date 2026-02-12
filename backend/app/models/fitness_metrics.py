"""DailyFitness ORM model — daily CTL/ATL/TSB fitness tracking."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyFitness(Base):
    __tablename__ = "daily_fitness"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", "threshold_method", name="pk_daily_fitness"),
    )

    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    threshold_method: Mapped[str] = mapped_column(
        String(50), server_default="manual", nullable=False
    )

    # Daily totals
    tss_total: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    activity_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    # Fitness metrics (EWMA)
    ctl: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    atl: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    tsb: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)

    def __repr__(self) -> str:
        return (
            f"<DailyFitness user_id={self.user_id} date={self.date} "
            f"ctl={self.ctl} atl={self.atl} tsb={self.tsb}>"
        )
