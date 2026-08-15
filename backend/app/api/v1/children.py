import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import AdminUser, AuditLog, Child
from app.schemas.child import ChildCreate, ChildResponse, ChildUpdate

router = APIRouter(prefix="/children", tags=["children"])


@router.get("", response_model=list[ChildResponse])
async def list_children(
    current_user: CurrentAdminUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[Child]:
    result = await db.scalars(
        select(Child)
        .where(
            Child.organization_id == current_user.organization_id,
            Child.deleted_at.is_(None),
        )
        .order_by(Child.last_name_kana, Child.first_name_kana, Child.created_at)
    )
    return list(result.all())


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
async def create_child(
    body: ChildCreate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Child:
    _require_editor(current_user)
    child = Child(organization_id=current_user.organization_id, **body.model_dump())
    db.add(child)
    await db.flush()
    _add_audit(db, current_user, "ADD_CHILD", child.id)
    await db.commit()
    await db.refresh(child)
    return child


@router.get("/{child_id}", response_model=ChildResponse)
async def get_child(
    child_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Child:
    return await _get_child(child_id, current_user, db)


@router.put("/{child_id}", response_model=ChildResponse)
async def update_child(
    child_id: uuid.UUID,
    body: ChildUpdate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Child:
    _require_editor(current_user)
    child = await _get_child(child_id, current_user, db)
    for field, value in body.model_dump().items():
        setattr(child, field, value)
    _add_audit(db, current_user, "UPDATE_CHILD", child.id)
    await db.commit()
    await db.refresh(child)
    return child


async def _get_child(child_id: uuid.UUID, user: AdminUser, db: AsyncSession) -> Child:
    child = await db.scalar(
        select(Child).where(
            Child.id == child_id,
            Child.organization_id == user.organization_id,
            Child.deleted_at.is_(None),
        )
    )
    if child is None:
        raise AppError("NOT_FOUND", "子供が見つかりません。", status.HTTP_404_NOT_FOUND)
    return child


def _require_editor(user: AdminUser) -> None:
    if user.role == "STAFF":
        raise AppError("FORBIDDEN", "この操作を行う権限がありません。", status.HTTP_403_FORBIDDEN)


def _add_audit(db: AsyncSession, user: AdminUser, action: str, child_id: uuid.UUID) -> None:
    db.add(
        AuditLog(
            organization_id=user.organization_id,
            actor_type="ADMIN",
            user_id=user.id,
            action=action,
            resource_type="CHILD",
            resource_id=child_id,
        )
    )
