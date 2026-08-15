from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentAdminUser
from app.core.exceptions import AppError
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.auth import AdminUserResponse, LoginRequest, TokenResponse

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenResponse:
    user = await db.scalar(
        select(AdminUser).where(
            func.lower(AdminUser.email) == body.email.lower(),
            AdminUser.deleted_at.is_(None),
        )
    )
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(
            "INVALID_CREDENTIALS",
            "メールアドレスまたはパスワードが正しくありません。",
            status.HTTP_401_UNAUTHORIZED,
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "admin_user_id": str(user.id),
            "organization_id": str(user.organization_id),
            "role": user.role,
        }
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AdminUserResponse)
async def get_me(current_user: CurrentAdminUser) -> AdminUser:
    return current_user
