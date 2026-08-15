from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models import Invitation


async def get_valid_invitation(
    code: str, db: AsyncSession, *, for_update: bool = False
) -> Invitation:
    query = select(Invitation).where(Invitation.invitation_code == code)
    if for_update:
        query = query.with_for_update()
    invitation = await db.scalar(query)
    if invitation is None:
        raise AppError("INVITATION_NOT_FOUND", "招待が見つかりません。", status.HTTP_404_NOT_FOUND)
    if invitation.status != "ACTIVE":
        raise AppError("INVITATION_INACTIVE", "この招待は利用できません。", status.HTTP_410_GONE)
    now = datetime.now(UTC)
    if invitation.expires_at is not None and invitation.expires_at <= now:
        invitation.status = "EXPIRED"
        await db.commit()
        raise AppError("INVITATION_EXPIRED", "この招待は期限切れです。", status.HTTP_410_GONE)
    if invitation.max_uses is not None and invitation.used_count >= invitation.max_uses:
        raise AppError(
            "INVITATION_LIMIT_REACHED",
            "この招待は利用上限に達しています。",
            status.HTTP_410_GONE,
        )
    return invitation


async def consume_invitation(code: str, db: AsyncSession) -> Invitation:
    """Consume after a caller has verified the parent's external identity.

    The row lock keeps the max-use check and increment atomic. Phase 9 calls this
    from the LINE onboarding transaction; no public API accepts an unverified ID.
    """
    invitation = await get_valid_invitation(code, db, for_update=True)
    invitation.used_count += 1
    return invitation
