"""UserSettings ORM model — per-user training configuration (FTP, zones, weight)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # FTP
    ftp_watts: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    ftp_method: Mapped[str] = mapped_column(
        String(50), server_default="manual", nullable=False
    )
    ftp_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Heart rate zones (JSON: {"z1": [0, 120], "z2": [120, 150], ...})
    hr_zones: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Body weight
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="settings")  # noqa: F821

    def __repr__(self) -> str:
        return f"<UserSettings user_id={self.user_id} ftp={self.ftp_watts}>"
