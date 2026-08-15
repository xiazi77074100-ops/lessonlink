import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import AdminUser, AuditLog, Child, Parent, ParentChild
from app.schemas.parent import ParentChildCreate, ParentDetailResponse, ParentResponse

router = APIRouter(prefix="/parents", tags=["parents"])


@router.get("", response_model=list[ParentResponse])
async def list_parents(
    current_user: CurrentAdminUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[Parent]:
    result = await db.scalars(
        select(Parent)
        .where(
            Parent.organization_id == current_user.organization_id,
            Parent.deleted_at.is_(None),
        )
        .order_by(Parent.display_name)
    )
    return list(result.all())


@router.get("/{parent_id}", response_model=ParentDetailResponse)
async def get_parent(
    parent_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ParentDetailResponse:
    parent = await _get_parent(parent_id, current_user, db)
    children = await db.scalars(
        select(Child)
        .join(ParentChild, ParentChild.child_id == Child.id)
        .where(
            ParentChild.parent_id == parent.id,
            ParentChild.organization_id == current_user.organization_id,
            Child.organization_id == current_user.organization_id,
            Child.deleted_at.is_(None),
        )
    )
    parent_data = ParentResponse.model_validate(parent).model_dump()
    return ParentDetailResponse(**parent_data, children=list(children.all()))


@router.post("/{parent_id}/children", status_code=status.HTTP_204_NO_CONTENT)
async def bind_child(
    parent_id: uuid.UUID,
    body: ParentChildCreate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    _require_editor(current_user)
    parent = await _get_parent(parent_id, current_user, db)
    child = await db.scalar(
        select(Child).where(
            Child.id == body.child_id,
            Child.organization_id == current_user.organization_id,
            Child.deleted_at.is_(None),
        )
    )
    if child is None:
        raise AppError("NOT_FOUND", "子供が見つかりません。", status.HTTP_404_NOT_FOUND)
    binding = ParentChild(
        organization_id=current_user.organization_id,
        parent_id=parent.id,
        child_id=child.id,
        verified_at=datetime.now(UTC),
    )
    db.add(binding)
    try:
        await db.flush()
        db.add(_audit(current_user, "CHILD_BOUND", binding.id, child.id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            "ALREADY_BOUND", "既に紐付けられています。", status.HTTP_409_CONFLICT
        ) from None


@router.delete("/{parent_id}/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_child(
    parent_id: uuid.UUID,
    child_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    _require_editor(current_user)
    await _get_parent(parent_id, current_user, db)
    result = await db.execute(
        delete(ParentChild).where(
            ParentChild.parent_id == parent_id,
            ParentChild.child_id == child_id,
            ParentChild.organization_id == current_user.organization_id,
        )
    )
    if result.rowcount == 0:
        raise AppError("NOT_FOUND", "紐付けが見つかりません。", status.HTTP_404_NOT_FOUND)
    db.add(_audit(current_user, "CHILD_UNBOUND", None, child_id))
    await db.commit()


async def _get_parent(parent_id: uuid.UUID, user: AdminUser, db: AsyncSession) -> Parent:
    parent = await db.scalar(
        select(Parent).where(
            Parent.id == parent_id,
            Parent.organization_id == user.organization_id,
            Parent.deleted_at.is_(None),
        )
    )
    if parent is None:
        raise AppError("NOT_FOUND", "保護者が見つかりません。", status.HTTP_404_NOT_FOUND)
    return parent


def _require_editor(user: AdminUser) -> None:
    if user.role == "STAFF":
        raise AppError("FORBIDDEN", "この操作を行う権限がありません。", status.HTTP_403_FORBIDDEN)


def _audit(
    user: AdminUser, action: str, binding_id: uuid.UUID | None, child_id: uuid.UUID
) -> AuditLog:
    return AuditLog(
        organization_id=user.organization_id,
        actor_type="ADMIN",
        user_id=user.id,
        action=action,
        resource_type="PARENT_CHILD",
        resource_id=binding_id,
        meta={"child_id": str(child_id)},
    )
