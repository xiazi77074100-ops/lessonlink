from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.models import AdminUser, AuditLog, Organization
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationCreateResponse,
    OrganizationResponse,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> OrganizationCreateResponse:
    owner_fields = {"owner_email", "owner_password", "owner_display_name"}
    organization = Organization(**body.model_dump(exclude=owner_fields))
    db.add(organization)
    try:
        await db.flush()
        owner = AdminUser(
            organization_id=organization.id,
            email=body.owner_email.lower(),
            password_hash=hash_password(body.owner_password),
            display_name=body.owner_display_name,
            role="OWNER",
        )
        db.add(owner)
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            "EMAIL_ALREADY_EXISTS",
            "このメールアドレスは既に使用されています。",
            status.HTTP_409_CONFLICT,
        ) from None

    token = create_access_token(
        {
            "sub": str(owner.id),
            "admin_user_id": str(owner.id),
            "organization_id": str(organization.id),
            "role": owner.role,
        }
    )
    return OrganizationCreateResponse(organization=organization, access_token=token)


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: CurrentAdminUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[Organization]:
    organization = await _get_current_organization(current_user, db)
    return [organization]


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    body: OrganizationUpdate,
    current_user: CurrentAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization:
    if str(current_user.organization_id) != organization_id:
        raise AppError("NOT_FOUND", "組織が見つかりません。", status.HTTP_404_NOT_FOUND)
    if current_user.role == "STAFF":
        raise AppError("FORBIDDEN", "この操作を行う権限がありません。", status.HTTP_403_FORBIDDEN)

    organization = await _get_current_organization(current_user, db)
    changes = body.model_dump()
    for field, value in changes.items():
        setattr(organization, field, value)
    db.add(
        AuditLog(
            organization_id=organization.id,
            actor_type="ADMIN",
            user_id=current_user.id,
            action="UPDATE_ORGANIZATION",
            resource_type="ORGANIZATION",
            resource_id=organization.id,
            meta={"fields": list(changes)},
        )
    )
    await db.commit()
    await db.refresh(organization)
    return organization


async def _get_current_organization(current_user: AdminUser, db: AsyncSession) -> Organization:
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == current_user.organization_id,
            Organization.deleted_at.is_(None),
        )
    )
    if organization is None:
        raise AppError("NOT_FOUND", "組織が見つかりません。", status.HTTP_404_NOT_FOUND)
    return organization
