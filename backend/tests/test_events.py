import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Attendance, AuditLog, Event


class ScalarResult:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class FakeSession:
    def __init__(
        self,
        scalar_results: list[Any] | None = None,
        collection_results: list[list[Any]] | None = None,
    ) -> None:
        self.scalar_results = iter(scalar_results or [])
        self.collection_results = iter(collection_results or [])
        self.added: list[Any] = []
        self.committed = False

    async def scalar(self, _: Any) -> Any:
        return next(self.scalar_results)

    async def scalars(self, _: Any) -> ScalarResult:
        return ScalarResult(next(self.collection_results))

    def add(self, value: Any) -> None:
        self.added.append(value)

    def add_all(self, values: list[Any]) -> None:
        self.added.extend(values)

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if isinstance(value, Event):
                value.created_at = now
                value.updated_at = now

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _: Any) -> None:
        pass


def make_user(role: str = "OWNER") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), role=role, deleted_at=None
    )


def make_event(organization_id: uuid.UUID, event_status: str = "PUBLISHED") -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        title="通常練習",
        description=None,
        start_at=now + timedelta(days=1),
        end_at=now + timedelta(days=1, hours=2),
        location_name="体育館",
        location_address=None,
        status=event_status,
        created_at=now,
        updated_at=now,
    )


def auth_header(user: SimpleNamespace) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "organization_id": str(user.organization_id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_events_returns_current_tenant_rows() -> None:
    user = make_user()
    event = make_event(user.organization_id)
    app.dependency_overrides[get_db] = lambda: FakeSession([user], [[event]])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/events?scope=future", headers=auth_header(user))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(event.id)


@pytest.mark.asyncio
async def test_create_event_precreates_attendance_for_active_children() -> None:
    user = make_user()
    child_ids = [uuid.uuid4(), uuid.uuid4()]
    session = FakeSession([user], [child_ids])
    app.dependency_overrides[get_db] = lambda: session
    start = datetime.now(UTC) + timedelta(days=1)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/events",
                headers=auth_header(user),
                json={
                    "title": "通常練習",
                    "start_at": start.isoformat(),
                    "end_at": (start + timedelta(hours=2)).isoformat(),
                    "status": "PUBLISHED",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    attendances = [value for value in session.added if isinstance(value, Attendance)]
    assert {attendance.child_id for attendance in attendances} == set(child_ids)
    assert all(attendance.organization_id == user.organization_id for attendance in attendances)
    assert any(isinstance(value, AuditLog) for value in session.added)


@pytest.mark.asyncio
async def test_get_event_hides_other_tenant_event() -> None:
    user = make_user()
    app.dependency_overrides[get_db] = lambda: FakeSession([user, None])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/events/{uuid.uuid4()}", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_event_sets_status_and_audits() -> None:
    user = make_user()
    event = make_event(user.organization_id)
    session = FakeSession([user, event])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/events/{event.id}/cancel", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert event.status == "CANCELLED"
    assert session.committed
    assert any(
        isinstance(value, AuditLog) and value.action == "CANCEL_EVENT"
        for value in session.added
    )
