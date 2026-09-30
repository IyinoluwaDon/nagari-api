import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class RequestStatus(str, enum.Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    COMPLETED = "Completed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DemoRequest(Base):
    __tablename__ = "demo_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    school_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, values_callable=lambda e: [m.value for m in e]),
        default=RequestStatus.NEW,
        index=True,
    )
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
