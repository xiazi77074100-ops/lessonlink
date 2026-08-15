from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings


class NotificationSendError(Exception):
    pass


class NotificationChannel(Protocol):
    async def send(self, recipient_id: str, message: str) -> None: ...


@dataclass
class LineNotificationChannel:
    access_token: str

    async def send(self, recipient_id: str, message: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.line.me/v2/bot/message/push",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    json={"to": recipient_id, "messages": [{"type": "text", "text": message}]},
                )
        except httpx.HTTPError as exc:
            raise NotificationSendError from exc
        if response.status_code != 200:
            raise NotificationSendError(f"LINE returned {response.status_code}")


class MockNotificationChannel:
    async def send(self, recipient_id: str, message: str) -> None:
        return None


def get_notification_channel() -> NotificationChannel:
    settings = get_settings()
    if settings.line_mock_enabled and settings.environment == "development":
        return MockNotificationChannel()
    if not settings.line_messaging_channel_access_token:
        raise NotificationSendError("LINE Messaging API is not configured")
    return LineNotificationChannel(settings.line_messaging_channel_access_token)
