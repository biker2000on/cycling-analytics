"""Threshold ORM model -- per-user FTP threshold history with multiple estimation methods."""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ThresholdMethod(str, enum.Enum):
    manual = "manual"
    pct_20min = "pct_20min"
    pct_8min = "pct_8min"
    xert_model = "xert_model"


class Threshold(Base):
    __tablename__ = "thresholds"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "method", "effective_date",
            name="uq_thresholds_user_method_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    ftp_watts: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    source_activity_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship()  # noqa: F821
    source_activity: Mapped["Activity"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Threshold user_id={self.user_id} method={self.method} "
            f"ftp={self.ftp_watts} date={self.effective_date}>"
        )
