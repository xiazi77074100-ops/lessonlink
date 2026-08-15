import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import notifications, parent_portal
from app.db.session import engine, get_db
from app.main import app
from app.models import Attendance, ParentChild
from app.services.line_auth import LineIdentity
from app.services.notifications import MockNotificationChannel

pytestmark = [
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 with PostgreSQL available",
    ),
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        app.dependency_overrides[get_db] = lambda: session
        try:
            yield session
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()


async def test_attendance_upsert_is_idempotent_in_postgresql(db_session: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token, child_id, event_id = await _create_core_data(client)
        headers = {"Authorization": f"Bearer {admin_token}"}
        first = await client.post(
            "/api/v1/attendance",
            headers=headers,
            json={"event_id": event_id, "child_id": child_id, "status": "ATTENDING"},
        )
        second = await client.post(
            "/api/v1/attendance",
            headers=headers,
            json={"event_id": event_id, "child_id": child_id, "status": "LATE"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    count = await db_session.scalar(
        select(func.count()).select_from(Attendance).where(
            Attendance.event_id == uuid.UUID(event_id),
            Attendance.child_id == uuid.UUID(child_id),
        )
    )
    attendance = await db_session.scalar(
        select(Attendance).where(
            Attendance.event_id == uuid.UUID(event_id),
            Attendance.child_id == uuid.UUID(child_id),
        )
    )
    assert count == 1
    assert attendance is not None and attendance.status == "LATE"


async def test_parent_cannot_bind_child_from_another_tenant(db_session: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_a, _, _ = await _create_core_data(client, suffix="a")
        token_b, child_b, _ = await _create_core_data(client, suffix="b")
        invitation = await client.post(
            "/api/v1/invitations",
            headers={"Authorization": f"Bearer {token_a}"},
            json={},
        )
        code = invitation.json()["invitation_code"]

        async def verify(_: str) -> LineIdentity:
            return LineIdentity("integration-parent-a", "保護者A")

        original = parent_portal.verify_line_id_token
        parent_portal.verify_line_id_token = verify
        try:
            login = await client.post(
                "/api/v1/parent/auth/line",
                json={"id_token": "test-token", "invitation_code": code},
            )
        finally:
            parent_portal.verify_line_id_token = original
        parent_token = login.json()["access_token"]
        response = await client.post(
            "/api/v1/parent/children/bind",
            headers={"Authorization": f"Bearer {parent_token}"},
            json={"child_id": child_b, "birth_date": "2018-04-01"},
        )

    assert token_b
    assert response.status_code == 400
    cross_binding_count = await db_session.scalar(
        select(func.count()).select_from(ParentChild).where(
            ParentChild.child_id == uuid.UUID(child_b)
        )
    )
    assert cross_binding_count == 0


async def test_mvp_happy_path(db_session: AsyncSession) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token, child_id, event_id = await _create_core_data(client, suffix="happy")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        invitation = await client.post("/api/v1/invitations", headers=admin_headers, json={})

        async def verify(_: str) -> LineIdentity:
            return LineIdentity("integration-happy-parent", "テスト保護者")

        original = parent_portal.verify_line_id_token
        parent_portal.verify_line_id_token = verify
        try:
            login = await client.post(
                "/api/v1/parent/auth/line",
                json={
                    "id_token": "test-token",
                    "invitation_code": invitation.json()["invitation_code"],
                },
            )
        finally:
            parent_portal.verify_line_id_token = original
        parent_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        binding = await client.post(
            "/api/v1/parent/children/bind",
            headers=parent_headers,
            json={"child_id": child_id, "birth_date": "2018-04-01"},
        )
        answer = await client.post(
            "/api/v1/parent/attendance",
            headers=parent_headers,
            json={"event_id": event_id, "child_id": child_id, "status": "ATTENDING"},
        )
        summary = await client.get(
            f"/api/v1/events/{event_id}/attendance", headers=admin_headers
        )
        await client.post(
            "/api/v1/parent/attendance",
            headers=parent_headers,
            json={"event_id": event_id, "child_id": child_id, "status": "NO_RESPONSE"},
        )
        original_channel_factory = notifications.get_notification_channel
        notifications.get_notification_channel = lambda: MockNotificationChannel()
        try:
            reminder = await client.post(
                f"/api/v1/events/{event_id}/remind", headers=admin_headers
            )
        finally:
            notifications.get_notification_channel = original_channel_factory

    assert invitation.status_code == 201
    assert login.status_code == 200
    assert binding.status_code == 204
    assert answer.status_code == 204
    assert summary.status_code == 200
    assert summary.json()["summary"]["attending"] == 1
    assert reminder.status_code == 200
    assert reminder.json()["sent"] == 1


async def _create_core_data(
    client: AsyncClient, suffix: str | None = None
) -> tuple[str, str, str]:
    unique = suffix or uuid.uuid4().hex[:8]
    organization = await client.post(
        "/api/v1/organizations",
        json={
            "name": f"統合テストクラブ-{unique}",
            "organization_type": "サッカー",
            "owner_email": f"integration-{unique}@example.com",
            "owner_password": "password123",
            "owner_display_name": "テスト管理者",
        },
    )
    token = organization.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    child = await client.post(
        "/api/v1/children",
        headers=headers,
        json={
            "first_name": "太郎",
            "last_name": "田中",
            "birth_date": "2018-04-01",
            "status": "ACTIVE",
        },
    )
    start = datetime.now(UTC) + timedelta(days=1)
    event = await client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "title": "統合テスト練習",
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=2)).isoformat(),
            "status": "PUBLISHED",
        },
    )
    assert organization.status_code == 201
    assert child.status_code == 201
    assert event.status_code == 201
    return token, child.json()["id"], event.json()["id"]
