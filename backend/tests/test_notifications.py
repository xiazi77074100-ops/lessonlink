import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import AuditLog, Notification


class Result:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class FakeSession:
    def __init__(self, scalar_results: list[Any], rows: list[Any] | None = None) -> None:
        self.scalar_results = iter(scalar_results)
        self.rows = rows or []
        self.added: list[Any] = []
        self.committed = False

    async def scalar(self, _: Any) -> Any:
        return next(self.scalar_results)

    async def execute(self, _: Any) -> Result:
        return Result(self.rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True


class RecordingChannel:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def send(self, recipient_id: str, message: str) -> None:
        self.messages.append((recipient_id, message))


def make_user(role: str = "OWNER") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), role=role, deleted_at=None
    )


def make_event(user: SimpleNamespace, event_status: str = "PUBLISHED") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        title="通常練習",
        start_at=datetime.now(UTC) + timedelta(days=1),
        status=event_status,
    )


def auth_header(user: SimpleNamespace) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "organization_id": str(user.organization_id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_reminder_groups_multiple_children_into_one_parent_message(monkeypatch: Any) -> None:
    user = make_user()
    event = make_event(user)
    parent = SimpleNamespace(id=uuid.uuid4(), line_user_id="U-parent-1")
    children = [
        SimpleNamespace(id=uuid.uuid4(), first_name="太郎", last_name="田中"),
        SimpleNamespace(id=uuid.uuid4(), first_name="花子", last_name="田中"),
    ]
    session = FakeSession([user, event], [(parent, child) for child in children])
    channel = RecordingChannel()
    monkeypatch.setattr("app.api.v1.notifications.get_notification_channel", lambda: channel)
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/events/{event.id}/remind", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "event_id": str(event.id), "target_parents": 1, "sent": 1, "failed": 0
    }
    assert len(channel.messages) == 1
    assert "田中 太郎" in channel.messages[0][1]
    assert "田中 花子" in channel.messages[0][1]
    log = next(value for value in session.added if isinstance(value, Notification))
    assert len(log.payload["child_ids"]) == 2
    assert log.status == "SENT"
    assert any(isinstance(value, AuditLog) for value in session.added)


@pytest.mark.asyncio
async def test_reminder_without_config_records_failed_delivery(monkeypatch: Any) -> None:
    user = make_user()
    event = make_event(user)
    parent = SimpleNamespace(id=uuid.uuid4(), line_user_id="U-parent-1")
    child = SimpleNamespace(id=uuid.uuid4(), first_name="太郎", last_name="田中")
    session = FakeSession([user, event], [(parent, child)])

    from app.services.notifications import NotificationSendError

    def unavailable() -> None:
        raise NotificationSendError

    monkeypatch.setattr("app.api.v1.notifications.get_notification_channel", unavailable)
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/events/{event.id}/remind", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["failed"] == 1
    log = next(value for value in session.added if isinstance(value, Notification))
    assert log.status == "FAILED"


@pytest.mark.asyncio
async def test_staff_cannot_send_reminders() -> None:
    user = make_user("STAFF")
    app.dependency_overrides[get_db] = lambda: FakeSession([user])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/events/{uuid.uuid4()}/remind", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
