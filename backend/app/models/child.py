from datetime import date

from sqlalchemy import CheckConstraint, Date, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDPKMixin


class Child(UUIDPKMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "children"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_children_status"),
        Index("ix_children_org_status", "organization_id", "status"),
    )

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name_kana: Mapped[str | None] = mapped_column(String(50))
    last_name_kana: Mapped[str | None] = mapped_column(String(50))
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    grade: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
