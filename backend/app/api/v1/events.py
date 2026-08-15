import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import AdminUser, Attendance, AuditLog, Child, Event
from app.schemas.event import EventCreate, EventResponse, EventUpdate

router = APIRouter(prefix="/events", tags=["events"])
EventScope = Literal["all", "today", "week", "month", "future"]


@router.get("", response_model=list[EventResponse])
async def list_events(
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    scope: Annotated[EventScope, Query()] = "all",
) -> list[Event]:
    query = select(Event).where(Event.organization_id == current_user.organization_id)
    start, end = _scope_range(scope)
    if start is not None:
        query = query.where(Event.start_at >= start)
    if end is not None:
        query = query.where(Event.start_at < end)
    result = await db.scalars(query.order_by(Event.start_at))
    return list(result.all())


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    _require_editor(current_user)
    event = Event(organization_id=current_user.organization_id, **body.model_dump())
    db.add(event)
    await db.flush()
    child_ids = await db.scalars(
        select(Child.id).where(
            Child.organization_id == current_user.organization_id,
            Child.status == "ACTIVE",
            Child.deleted_at.is_(None),
        )
    )
    db.add_all(
        [
            Attendance(
                organization_id=current_user.organization_id,
                event_id=event.id,
                child_id=child_id,
                status="NO_RESPONSE",
            )
            for child_id in child_ids.all()
        ]
    )
    _add_audit(db, current_user, "CREATE_EVENT", event.id)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    return await _get_event(event_id, current_user, db)


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    _require_editor(current_user)
    event = await _get_event(event_id, current_user, db)
    if event.status == "CANCELLED":
        raise AppError(
            "EVENT_CANCELLED",
            "キャンセル済みの活動は編集できません。",
            status.HTTP_409_CONFLICT,
        )
    for field, value in body.model_dump().items():
        setattr(event, field, value)
    _add_audit(db, current_user, "UPDATE_EVENT", event.id)
    await db.commit()
    await db.refresh(event)
    return event


@router.post("/{event_id}/cancel", response_model=EventResponse)
async def cancel_event(
    event_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    _require_editor(current_user)
    event = await _get_event(event_id, current_user, db)
    if event.status != "CANCELLED":
        event.status = "CANCELLED"
        _add_audit(db, current_user, "CANCEL_EVENT", event.id)
        await db.commit()
        await db.refresh(event)
    return event


async def _get_event(event_id: uuid.UUID, user: AdminUser, db: AsyncSession) -> Event:
    event = await db.scalar(
        select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id)
    )
    if event is None:
        raise AppError("NOT_FOUND", "活動が見つかりません。", status.HTTP_404_NOT_FOUND)
    return event


def _require_editor(user: AdminUser) -> None:
    if user.role == "STAFF":
        raise AppError("FORBIDDEN", "この操作を行う権限がありません。", status.HTTP_403_FORBIDDEN)


def _add_audit(db: AsyncSession, user: AdminUser, action: str, event_id: uuid.UUID) -> None:
    db.add(
        AuditLog(
            organization_id=user.organization_id,
            actor_type="ADMIN",
            user_id=user.id,
            action=action,
            resource_type="EVENT",
            resource_id=event_id,
        )
    )


def _scope_range(scope: EventScope) -> tuple[datetime | None, datetime | None]:
    if scope == "all":
        return None, None
    now = datetime.now(UTC)
    if scope == "future":
        return now, None
    jst = ZoneInfo("Asia/Tokyo")
    today = now.astimezone(jst).date()
    start_date = today
    if scope == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
    elif scope == "month":
        start_date = today.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month
    else:
        end_date = today + timedelta(days=1)
    return (
        datetime.combine(start_date, time.min, jst).astimezone(UTC),
        datetime.combine(end_date, time.min, jst).astimezone(UTC),
    )
