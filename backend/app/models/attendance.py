import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class Attendance(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "attendances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ATTENDING', 'ABSENT', 'LATE', 'NO_RESPONSE')",
            name="ck_attendances_status",
        ),
        UniqueConstraint("event_id", "child_id", name="uq_attendances_event_child"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("children.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="NO_RESPONSE")
    note: Mapped[str | None] = mapped_column(String(500))
    responded_by_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parents.id")
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
