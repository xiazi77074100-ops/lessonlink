import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import AdminUser, AuditLog, Child, Invitation, InvitationChild, Organization
from app.schemas.invitation import (
    DEFAULT_FAMILY_GUARDIAN_LIMIT,
    InvitationChildSummary,
    InvitationCreate,
    InvitationPublicResponse,
    InvitationResponse,
)
from app.services.invitations import get_valid_invitation

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("", response_model=list[InvitationResponse])
async def list_invitations(
    current_user: CurrentAdminUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[InvitationResponse]:
    result = await db.scalars(
        select(Invitation)
        .where(Invitation.organization_id == current_user.organization_id)
        .order_by(Invitation.created_at.desc())
    )
    invitations = list(result.all())
    children_by_invitation = await _load_children_by_invitation(
        [invitation.id for invitation in invitations], db
    )
    return [
        _to_response(invitation, children_by_invitation.get(invitation.id, []))
        for invitation in invitations
    ]


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationResponse:
    _require_editor(current_user)
    children: list[Child] = []
    if body.child_ids:
        result = await db.scalars(
            select(Child).where(
                Child.id.in_(body.child_ids),
                Child.organization_id == current_user.organization_id,
                Child.status == "ACTIVE",
                Child.deleted_at.is_(None),
            )
        )
        children = list(result.all())
        if len(children) != len(set(body.child_ids)):
            raise AppError(
                "CHILD_NOT_FOUND", "指定された子供が見つかりません。", status.HTTP_400_BAD_REQUEST
            )

    max_uses = body.max_uses
    if max_uses is None and children:
        max_uses = DEFAULT_FAMILY_GUARDIAN_LIMIT

    invitation = Invitation(
        organization_id=current_user.organization_id,
        invitation_code=secrets.token_urlsafe(24)[:32],
        expires_at=body.expires_at,
        max_uses=max_uses,
        used_count=0,
        status="ACTIVE",
        created_by_admin_id=current_user.id,
    )
    db.add(invitation)
    await db.flush()
    for child in children:
        db.add(
            InvitationChild(
                organization_id=current_user.organization_id,
                invitation_id=invitation.id,
                child_id=child.id,
            )
        )
    _add_audit(db, current_user, "CREATE_INVITATION", invitation.id)
    await db.commit()
    await db.refresh(invitation)
    return _to_response(invitation, children)


@router.post("/{invitation_id}/disable", response_model=InvitationResponse)
async def disable_invitation(
    invitation_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationResponse:
    _require_editor(current_user)
    invitation = await db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == current_user.organization_id,
        )
    )
    if invitation is None:
        raise AppError("NOT_FOUND", "招待が見つかりません。", status.HTTP_404_NOT_FOUND)
    if invitation.status == "ACTIVE":
        invitation.status = "DISABLED"
        _add_audit(db, current_user, "DISABLE_INVITATION", invitation.id)
        await db.commit()
        await db.refresh(invitation)
    children_by_invitation = await _load_children_by_invitation([invitation.id], db)
    return _to_response(invitation, children_by_invitation.get(invitation.id, []))


@router.get("/code/{code}", response_model=InvitationPublicResponse)
async def validate_invitation(
    code: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> InvitationPublicResponse:
    invitation = await get_valid_invitation(code, db)
    organization_name = await db.scalar(
        select(Organization.name).where(
            Organization.id == invitation.organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    if organization_name is None:
        raise AppError("INVITATION_INACTIVE", "この招待は利用できません。", status.HTTP_410_GONE)
    children_by_invitation = await _load_children_by_invitation([invitation.id], db)
    return InvitationPublicResponse(
        invitation_code=invitation.invitation_code,
        organization_name=organization_name,
        expires_at=invitation.expires_at,
        children=[
            InvitationChildSummary.model_validate(child, from_attributes=True)
            for child in children_by_invitation.get(invitation.id, [])
        ],
    )


def _require_editor(user: AdminUser) -> None:
    if user.role == "STAFF":
        raise AppError("FORBIDDEN", "この操作を行う権限がありません。", status.HTTP_403_FORBIDDEN)


def _add_audit(db: AsyncSession, user: AdminUser, action: str, invitation_id: uuid.UUID) -> None:
    db.add(
        AuditLog(
            organization_id=user.organization_id,
            actor_type="ADMIN",
            user_id=user.id,
            action=action,
            resource_type="INVITATION",
            resource_id=invitation_id,
        )
    )


async def _load_children_by_invitation(
    invitation_ids: list[uuid.UUID], db: AsyncSession
) -> dict[uuid.UUID, list[Child]]:
    if not invitation_ids:
        return {}
    rows = await db.execute(
        select(InvitationChild.invitation_id, Child)
        .join(Child, Child.id == InvitationChild.child_id)
        .where(InvitationChild.invitation_id.in_(invitation_ids))
    )
    children_by_invitation: dict[uuid.UUID, list[Child]] = {}
    for invitation_id, child in rows.all():
        children_by_invitation.setdefault(invitation_id, []).append(child)
    return children_by_invitation


def _to_response(invitation: Invitation, children: list[Child]) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        invitation_code=invitation.invitation_code,
        expires_at=invitation.expires_at,
        max_uses=invitation.max_uses,
        used_count=invitation.used_count,
        status=invitation.status,
        created_at=invitation.created_at,
        children=[
            InvitationChildSummary.model_validate(child, from_attributes=True)
            for child in children
        ],
    )
