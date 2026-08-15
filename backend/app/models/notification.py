import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class Notification(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('EVENT_CREATED', 'ATTENDANCE_REMINDER', 'EVENT_CANCELLED')",
            name="ck_notifications_type",
        ),
        CheckConstraint("channel IN ('LINE', 'EMAIL', 'PUSH')", name="ck_notifications_channel"),
        CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED')", name="ck_notifications_status"
        ),
    )

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parents.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default="LINE")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
