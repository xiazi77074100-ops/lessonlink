import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import AdminUser, AuditLog, Invitation, Organization
from app.schemas.invitation import InvitationCreate, InvitationPublicResponse, InvitationResponse
from app.services.invitations import get_valid_invitation

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("", response_model=list[InvitationResponse])
async def list_invitations(
    current_user: CurrentAdminUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[Invitation]:
    result = await db.scalars(
        select(Invitation)
        .where(Invitation.organization_id == current_user.organization_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Invitation:
    _require_editor(current_user)
    invitation = Invitation(
        organization_id=current_user.organization_id,
        invitation_code=secrets.token_urlsafe(24)[:32],
        expires_at=body.expires_at,
        max_uses=body.max_uses,
        used_count=0,
        status="ACTIVE",
        created_by_admin_id=current_user.id,
    )
    db.add(invitation)
    await db.flush()
    _add_audit(db, current_user, "CREATE_INVITATION", invitation.id)
    await db.commit()
    await db.refresh(invitation)
    return invitation


@router.post("/{invitation_id}/disable", response_model=InvitationResponse)
async def disable_invitation(
    invitation_id: uuid.UUID,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Invitation:
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
    return invitation


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
    return InvitationPublicResponse(
        invitation_code=invitation.invitation_code,
        organization_name=organization_name,
        expires_at=invitation.expires_at,
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
