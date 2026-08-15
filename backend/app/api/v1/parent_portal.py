import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentParent
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import Attendance, AuditLog, Child, Event, Parent, ParentChild
from app.schemas.parent_auth import (
    AvailableChildResponse,
    BindChildRequest,
    LineLoginRequest,
    ParentAttendanceRequest,
    ParentChildSummary,
    ParentEventChildResponse,
    ParentEventResponse,
    ParentMeResponse,
    ParentTokenResponse,
)
from app.services.invitations import get_valid_invitation
from app.services.line_auth import verify_line_id_token

router = APIRouter(prefix="/parent", tags=["parent"])


@router.post("/auth/line", response_model=ParentTokenResponse)
async def line_login(
    body: LineLoginRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> ParentTokenResponse:
    identity = await verify_line_id_token(body.id_token)
    invitation = await get_valid_invitation(body.invitation_code, db, for_update=True)
    parent = await db.scalar(
        select(Parent).where(
            Parent.organization_id == invitation.organization_id,
            Parent.line_user_id == identity.user_id,
            Parent.deleted_at.is_(None),
        )
    )
    if parent is None:
        invitation.used_count += 1
        parent = Parent(
            organization_id=invitation.organization_id,
            line_user_id=identity.user_id,
            display_name=identity.display_name,
            email=identity.email,
        )
        db.add(parent)
        await db.flush()
        db.add(_audit(parent, "PARENT_JOINED", "PARENT", parent.id))
        await db.commit()
        await db.refresh(parent)
    return ParentTokenResponse(
        access_token=create_access_token(
            {
                "sub": str(parent.id),
                "organization_id": str(parent.organization_id),
                "token_type": "parent",
            },
            expires_minutes=60 * 24 * 7,
        )
    )


@router.get("/me", response_model=ParentMeResponse)
async def get_parent_me(
    current_parent: CurrentParent, db: Annotated[AsyncSession, Depends(get_db)]
) -> ParentMeResponse:
    children = await _get_bound_children(current_parent, db)
    return ParentMeResponse(
        id=current_parent.id,
        organization_id=current_parent.organization_id,
        display_name=current_parent.display_name,
        children=[
            ParentChildSummary.model_validate(child, from_attributes=True) for child in children
        ],
    )


@router.get("/children/available", response_model=list[AvailableChildResponse])
async def list_available_children(
    current_parent: CurrentParent, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[Child]:
    result = await db.scalars(
        select(Child)
        .where(
            Child.organization_id == current_parent.organization_id,
            Child.status == "ACTIVE",
            Child.deleted_at.is_(None),
        )
        .order_by(Child.last_name_kana, Child.first_name_kana, Child.created_at)
    )
    return list(result.all())


@router.post("/children/bind", status_code=status.HTTP_204_NO_CONTENT)
async def bind_child(
    body: BindChildRequest,
    current_parent: CurrentParent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    child = await db.scalar(
        select(Child).where(
            Child.id == body.child_id,
            Child.organization_id == current_parent.organization_id,
            Child.status == "ACTIVE",
            Child.deleted_at.is_(None),
        )
    )
    if child is None or child.birth_date != body.birth_date:
        db.add(_audit(current_parent, "CHILD_BIND_FAILED", "CHILD", body.child_id))
        await db.commit()
        raise AppError(
            "CHILD_VERIFICATION_FAILED",
            "子供の情報を確認できませんでした。",
            status.HTTP_400_BAD_REQUEST,
        )
    existing = await db.scalar(
        select(ParentChild.id).where(
            ParentChild.parent_id == current_parent.id,
            ParentChild.child_id == child.id,
            ParentChild.organization_id == current_parent.organization_id,
        )
    )
    if existing is None:
        binding = ParentChild(
            organization_id=current_parent.organization_id,
            parent_id=current_parent.id,
            child_id=child.id,
            verified_at=datetime.now(UTC),
        )
        db.add(binding)
        await db.flush()
        db.add(_audit(current_parent, "CHILD_BOUND", "PARENT_CHILD", binding.id))
        await db.commit()


@router.get("/events", response_model=list[ParentEventResponse])
async def list_parent_events(
    current_parent: CurrentParent, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[ParentEventResponse]:
    result = await db.execute(
        select(Event, Attendance, Child)
        .join(Attendance, Attendance.event_id == Event.id)
        .join(Child, Child.id == Attendance.child_id)
        .join(ParentChild, ParentChild.child_id == Child.id)
        .where(
            Event.organization_id == current_parent.organization_id,
            Event.status == "PUBLISHED",
            Event.end_at >= datetime.now(UTC),
            Attendance.organization_id == current_parent.organization_id,
            ParentChild.organization_id == current_parent.organization_id,
            ParentChild.parent_id == current_parent.id,
        )
        .order_by(Event.start_at, Child.created_at)
    )
    grouped: dict[uuid.UUID, ParentEventResponse] = {}
    for event, attendance, child in result.all():
        if event.id not in grouped:
            grouped[event.id] = ParentEventResponse(
                id=event.id,
                title=event.title,
                description=event.description,
                start_at=event.start_at,
                end_at=event.end_at,
                location_name=event.location_name,
                location_address=event.location_address,
                children=[],
            )
        grouped[event.id].children.append(
            ParentEventChildResponse(
                child_id=child.id,
                child_name=f"{child.last_name} {child.first_name}",
                attendance_status=attendance.status,
            )
        )
    return list(grouped.values())


@router.post("/attendance", status_code=status.HTTP_204_NO_CONTENT)
async def answer_attendance(
    body: ParentAttendanceRequest,
    current_parent: CurrentParent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    event = await db.scalar(
        select(Event).where(
            Event.id == body.event_id,
            Event.organization_id == current_parent.organization_id,
            Event.status == "PUBLISHED",
        )
    )
    binding = await db.scalar(
        select(ParentChild.id).where(
            ParentChild.parent_id == current_parent.id,
            ParentChild.child_id == body.child_id,
            ParentChild.organization_id == current_parent.organization_id,
        )
    )
    if event is None or binding is None:
        raise AppError("NOT_FOUND", "活動または子供が見つかりません。", status.HTTP_404_NOT_FOUND)
    now = datetime.now(UTC)
    statement = (
        insert(Attendance)
        .values(
            organization_id=current_parent.organization_id,
            event_id=event.id,
            child_id=body.child_id,
            status=body.status,
            responded_by_parent_id=current_parent.id,
            responded_at=None if body.status == "NO_RESPONSE" else now,
        )
        .on_conflict_do_update(
            constraint="uq_attendances_event_child",
            set_={
                "status": body.status,
                "responded_by_parent_id": current_parent.id,
                "responded_at": None if body.status == "NO_RESPONSE" else now,
                "updated_at": now,
            },
        )
    )
    await db.execute(statement)
    db.add(_audit(current_parent, "ATTENDANCE_ANSWERED", "EVENT", event.id))
    await db.commit()


async def _get_bound_children(parent: Parent, db: AsyncSession) -> list[Child]:
    result = await db.scalars(
        select(Child)
        .join(ParentChild, ParentChild.child_id == Child.id)
        .where(
            ParentChild.parent_id == parent.id,
            ParentChild.organization_id == parent.organization_id,
            Child.organization_id == parent.organization_id,
            Child.deleted_at.is_(None),
        )
    )
    return list(result.all())


def _audit(parent: Parent, action: str, resource_type: str, resource_id: uuid.UUID) -> AuditLog:
    return AuditLog(
        organization_id=parent.organization_id,
        actor_type="PARENT",
        user_id=parent.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
