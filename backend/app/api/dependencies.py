import uuid
from typing import Annotated

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import AdminUser, Parent

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("UNAUTHORIZED", "認証が必要です。", status.HTTP_401_UNAUTHORIZED)

    try:
        payload = decode_access_token(credentials.credentials)
        admin_user_id = uuid.UUID(payload["sub"])
        organization_id = uuid.UUID(payload["organization_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise AppError(
            "INVALID_TOKEN", "認証トークンが無効です。", status.HTTP_401_UNAUTHORIZED
        ) from None

    user = await db.scalar(
        select(AdminUser).where(
            AdminUser.id == admin_user_id,
            AdminUser.organization_id == organization_id,
            AdminUser.deleted_at.is_(None),
        )
    )
    if user is None:
        raise AppError("INVALID_TOKEN", "認証トークンが無効です。", status.HTTP_401_UNAUTHORIZED)
    return user


CurrentAdminUser = Annotated[AdminUser, Depends(get_current_admin_user)]


async def get_current_parent(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Parent:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("UNAUTHORIZED", "認証が必要です。", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("token_type") != "parent":
            raise ValueError
        parent_id = uuid.UUID(payload["sub"])
        organization_id = uuid.UUID(payload["organization_id"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise AppError(
            "INVALID_TOKEN", "認証トークンが無効です。", status.HTTP_401_UNAUTHORIZED
        ) from None
    parent = await db.scalar(
        select(Parent).where(
            Parent.id == parent_id,
            Parent.organization_id == organization_id,
            Parent.deleted_at.is_(None),
        )
    )
    if parent is None:
        raise AppError("INVALID_TOKEN", "認証トークンが無効です。", status.HTTP_401_UNAUTHORIZED)
    return parent


CurrentParent = Annotated[Parent, Depends(get_current_parent)]
