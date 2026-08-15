import uuid
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import Attendance, AuditLog, Child, Event, Notification, Parent, ParentChild
from app.schemas.notification import ReminderResponse
from app.services.notifications import NotificationSendError, get_notification_channel

router = APIRouter(tags=["notifications"])


@router.post("/events/{event_id}/remind", response_model=ReminderResponse)
async def remind_no_response_parents(
    event_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReminderResponse:
    if current_user.role == "STAFF":
        raise AppError("FORBIDDEN", "この操作を行う権限がありません。", status.HTTP_403_FORBIDDEN)
    event = await db.scalar(
        select(Event).where(
            Event.id == event_id,
            Event.organization_id == current_user.organization_id,
        )
    )
    if event is None:
        raise AppError("NOT_FOUND", "活動が見つかりません。", status.HTTP_404_NOT_FOUND)
    if event.status == "CANCELLED":
        raise AppError(
            "EVENT_CANCELLED",
            "キャンセル済みの活動には通知できません。",
            status.HTTP_409_CONFLICT,
        )
    result = await db.execute(
        select(Parent, Child)
        .join(ParentChild, ParentChild.parent_id == Parent.id)
        .join(Child, Child.id == ParentChild.child_id)
        .join(
            Attendance,
            (Attendance.child_id == Child.id) & (Attendance.event_id == event.id),
        )
        .where(
            Parent.organization_id == current_user.organization_id,
            Parent.deleted_at.is_(None),
            ParentChild.organization_id == current_user.organization_id,
            Child.organization_id == current_user.organization_id,
            Child.deleted_at.is_(None),
            Attendance.organization_id == current_user.organization_id,
            Attendance.status == "NO_RESPONSE",
        )
    )
    grouped: dict[uuid.UUID, tuple[Parent, list[Child]]] = {}
    for parent, child in result.all():
        grouped.setdefault(parent.id, (parent, []))[1].append(child)

    sent = 0
    failed = 0
    try:
        channel = get_notification_channel()
    except NotificationSendError:
        channel = None
    for parent, children in grouped.values():
        child_names = "、".join(f"{child.last_name} {child.first_name}" for child in children)
        message = _reminder_message(event, child_names)
        delivery_status = "SENT"
        sent_at = datetime.now(UTC)
        try:
            if channel is None:
                raise NotificationSendError
            await channel.send(parent.line_user_id, message)
            sent += 1
        except NotificationSendError:
            delivery_status = "FAILED"
            sent_at = None
            failed += 1
        db.add(
            Notification(
                organization_id=current_user.organization_id,
                parent_id=parent.id,
                type="ATTENDANCE_REMINDER",
                channel="LINE",
                payload={
                    "event_id": str(event.id),
                    "child_ids": [str(child.id) for child in children],
                    "message": message,
                },
                status=delivery_status,
                sent_at=sent_at,
            )
        )
    db.add(
        AuditLog(
            organization_id=current_user.organization_id,
            actor_type="ADMIN",
            user_id=current_user.id,
            action="SEND_REMINDER",
            resource_type="EVENT",
            resource_id=event.id,
            meta={"target_parents": len(grouped), "sent": sent, "failed": failed},
        )
    )
    await db.commit()
    return ReminderResponse(
        event_id=event.id,
        target_parents=len(grouped),
        sent=sent,
        failed=failed,
    )


def _reminder_message(event: Event, child_names: str) -> str:
    event_date = event.start_at.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%m月%d日")
    return (
        f"{event_date}の「{event.title}」について、{child_names}さんの出欠回答がありません。\n"
        "習い事管理くんから出欠をご回答ください。"
    )
