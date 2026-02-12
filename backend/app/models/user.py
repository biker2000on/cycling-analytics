"""User ORM model.

Multi-user support with JWT authentication (Phase 5).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), server_default="UTC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    activities: Mapped[list["Activity"]] = relationship(  # noqa: F821
        back_populates="user", lazy="selectin"
    )
    health_metrics: Mapped[list["HealthMetric"]] = relationship(  # noqa: F821
        back_populates="user", lazy="selectin"
    )
    integrations: Mapped[list["Integration"]] = relationship(  # noqa: F821
        back_populates="user", lazy="selectin"
    )
    settings: Mapped["UserSettings | None"] = relationship(  # noqa: F821
        back_populates="user", lazy="selectin", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
