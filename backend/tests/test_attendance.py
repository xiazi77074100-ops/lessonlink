import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import AuditLog


class RowsResult:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class FakeSession:
    def __init__(self, scalar_results: list[Any], rows: list[Any] | None = None) -> None:
        self.scalar_results = iter(scalar_results)
        self.rows = rows or []
        self.added: list[Any] = []
        self.committed = False

    async def scalar(self, _: Any) -> Any:
        return next(self.scalar_results)

    async def execute(self, _: Any) -> RowsResult:
        return RowsResult(self.rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True


def make_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), role="OWNER", deleted_at=None
    )


def make_event(user: SimpleNamespace, event_status: str = "PUBLISHED") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), organization_id=user.organization_id, status=event_status
    )


def make_attendance(event_id: uuid.UUID, child_id: uuid.UUID, value: str) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        event_id=event_id,
        child_id=child_id,
        status=value,
        note=None,
        responded_at=None if value == "NO_RESPONSE" else now,
    )


def auth_header(user: SimpleNamespace) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "organization_id": str(user.organization_id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upsert_attendance_updates_existing_pair_and_audits() -> None:
    user = make_user()
    event = make_event(user)
    child_id = uuid.uuid4()
    attendance = make_attendance(event.id, child_id, "ATTENDING")
    session = FakeSession([user, event, child_id, attendance])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/attendance",
                headers=auth_header(user),
                json={"event_id": str(event.id), "child_id": str(child_id), "status": "ATTENDING"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ATTENDING"
    assert session.committed
    assert any(
        isinstance(value, AuditLog) and value.action == "UPDATE_ATTENDANCE"
        for value in session.added
    )


@pytest.mark.asyncio
async def test_cancelled_event_rejects_attendance_update() -> None:
    user = make_user()
    event = make_event(user, "CANCELLED")
    app.dependency_overrides[get_db] = lambda: FakeSession([user, event])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/attendance",
                headers=auth_header(user),
                json={
                    "event_id": str(event.id),
                    "child_id": str(uuid.uuid4()),
                    "status": "ABSENT",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EVENT_CANCELLED"


@pytest.mark.asyncio
async def test_attendance_summary_counts_all_statuses() -> None:
    user = make_user()
    event = make_event(user)
    statuses = ["ATTENDING", "ATTENDING", "ABSENT", "LATE", "NO_RESPONSE"]
    rows = []
    for index, attendance_status in enumerate(statuses):
        attendance = make_attendance(event.id, uuid.uuid4(), attendance_status)
        rows.append((attendance, f"名{index}", "田中"))
    session = FakeSession([user, event], rows)
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/events/{event.id}/attendance", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["summary"] == {
        "attending": 2,
        "absent": 1,
        "late": 1,
        "no_response": 1,
        "total": 5,
    }


@pytest.mark.asyncio
async def test_attendance_detail_hides_other_tenant_event() -> None:
    user = make_user()
    app.dependency_overrides[get_db] = lambda: FakeSession([user, None])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/events/{uuid.uuid4()}/attendance", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
