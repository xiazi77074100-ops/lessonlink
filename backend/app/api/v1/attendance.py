import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import AdminUser, Attendance, AuditLog, Child, Event
from app.schemas.attendance import (
    AttendanceResponse,
    AttendanceRowResponse,
    AttendanceSummary,
    AttendanceUpsert,
    EventAttendanceResponse,
)

router = APIRouter(tags=["attendance"])


@router.post("/attendance", response_model=AttendanceResponse)
async def upsert_attendance(
    body: AttendanceUpsert,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Attendance:
    event = await _get_event(body.event_id, current_user, db)
    if event.status == "CANCELLED":
        raise AppError(
            "EVENT_CANCELLED",
            "キャンセル済みの活動には回答できません。",
            status.HTTP_409_CONFLICT,
        )
    child_exists = await db.scalar(
        select(Child.id).where(
            Child.id == body.child_id,
            Child.organization_id == current_user.organization_id,
            Child.deleted_at.is_(None),
        )
    )
    if child_exists is None:
        raise AppError("NOT_FOUND", "子供が見つかりません。", status.HTTP_404_NOT_FOUND)

    now = datetime.now(UTC)
    values = {
        "organization_id": current_user.organization_id,
        "event_id": body.event_id,
        "child_id": body.child_id,
        "status": body.status,
        "note": body.note,
        "responded_at": None if body.status == "NO_RESPONSE" else now,
    }
    statement = (
        insert(Attendance)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_attendances_event_child",
            set_={
                "status": body.status,
                "note": body.note,
                "responded_by_parent_id": None,
                "responded_at": values["responded_at"],
                "updated_at": now,
            },
        )
        .returning(Attendance)
    )
    attendance = await db.scalar(statement)
    db.add(
        AuditLog(
            organization_id=current_user.organization_id,
            actor_type="ADMIN",
            user_id=current_user.id,
            action="UPDATE_ATTENDANCE",
            resource_type="ATTENDANCE",
            resource_id=attendance.id,
            meta={"event_id": str(body.event_id), "child_id": str(body.child_id)},
        )
    )
    await db.commit()
    return attendance


@router.get("/events/{event_id}/attendance", response_model=EventAttendanceResponse)
async def get_event_attendance(
    event_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EventAttendanceResponse:
    await _get_event(event_id, current_user, db)
    result = await db.execute(
        select(Attendance, Child.first_name, Child.last_name)
        .join(Child, Child.id == Attendance.child_id)
        .where(
            Attendance.event_id == event_id,
            Attendance.organization_id == current_user.organization_id,
            Child.organization_id == current_user.organization_id,
            Child.deleted_at.is_(None),
        )
        .order_by(Child.last_name_kana, Child.first_name_kana, Child.created_at)
    )
    rows = [
        AttendanceRowResponse(
            **AttendanceResponse.model_validate(attendance).model_dump(),
            child_first_name=first_name,
            child_last_name=last_name,
        )
        for attendance, first_name, last_name in result.all()
    ]
    counts = {key: 0 for key in ("ATTENDING", "ABSENT", "LATE", "NO_RESPONSE")}
    for row in rows:
        counts[row.status] += 1
    return EventAttendanceResponse(
        event_id=event_id,
        summary=AttendanceSummary(
            attending=counts["ATTENDING"],
            absent=counts["ABSENT"],
            late=counts["LATE"],
            no_response=counts["NO_RESPONSE"],
            total=len(rows),
        ),
        attendances=rows,
    )


async def _get_event(event_id: uuid.UUID, user: AdminUser, db: AsyncSession) -> Event:
    event = await db.scalar(
        select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id)
    )
    if event is None:
        raise AppError("NOT_FOUND", "活動が見つかりません。", status.HTTP_404_NOT_FOUND)
    return event
