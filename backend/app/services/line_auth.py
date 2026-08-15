from dataclasses import dataclass

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import AppError


@dataclass(frozen=True)
class LineIdentity:
    user_id: str
    display_name: str
    email: str | None = None


async def verify_line_id_token(id_token: str) -> LineIdentity:
    settings = get_settings()
    if settings.line_mock_enabled and settings.environment == "development":
        return _parse_mock_token(id_token)
    if not settings.line_login_channel_id:
        raise AppError(
            "LINE_NOT_CONFIGURED",
            "LINEログインが設定されていません。",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.line.me/oauth2/v2.1/verify",
                data={"id_token": id_token, "client_id": settings.line_login_channel_id},
            )
    except httpx.HTTPError:
        raise AppError(
            "LINE_UNAVAILABLE",
            "LINEログインを確認できませんでした。",
            status.HTTP_502_BAD_GATEWAY,
        ) from None
    if response.status_code != status.HTTP_200_OK:
        raise AppError(
            "INVALID_LINE_TOKEN", "LINEログインが無効です。", status.HTTP_401_UNAUTHORIZED
        )
    payload = response.json()
    if payload.get("aud") != settings.line_login_channel_id or not payload.get("sub"):
        raise AppError(
            "INVALID_LINE_TOKEN", "LINEログインが無効です。", status.HTTP_401_UNAUTHORIZED
        )
    return LineIdentity(
        user_id=payload["sub"],
        display_name=payload.get("name") or "LINEユーザー",
        email=payload.get("email"),
    )


def _parse_mock_token(token: str) -> LineIdentity:
    parts = token.split(":", 2)
    if len(parts) != 3 or parts[0] != "mock" or not parts[1]:
        raise AppError(
            "INVALID_LINE_TOKEN", "LINEログインが無効です。", status.HTTP_401_UNAUTHORIZED
        )
    return LineIdentity(user_id=parts[1], display_name=parts[2] or "開発ユーザー")
