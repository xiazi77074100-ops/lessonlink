import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import AuditLog, Invitation
from app.services.invitations import consume_invitation


class FakeSession:
    def __init__(self, scalar_results: list[Any]) -> None:
        self.scalar_results = iter(scalar_results)
        self.added: list[Any] = []
        self.committed = False

    async def scalar(self, _: Any) -> Any:
        return next(self.scalar_results)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if isinstance(value, Invitation):
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


def make_invitation(
    user: SimpleNamespace, *, invitation_status: str = "ACTIVE", expires_at: datetime | None = None
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        invitation_code="safe-test-code",
        expires_at=expires_at,
        max_uses=10,
        used_count=0,
        status=invitation_status,
        created_by_admin_id=user.id,
        created_at=now,
        updated_at=now,
    )


def auth_header(user: SimpleNamespace) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "organization_id": str(user.organization_id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_invitation_uses_secure_code_and_current_tenant() -> None:
    user = make_user()
    session = FakeSession([user])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/invitations",
                headers=auth_header(user),
                json={"max_uses": 5},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    invitation = next(value for value in session.added if isinstance(value, Invitation))
    assert invitation.organization_id == user.organization_id
    assert len(invitation.invitation_code) == 32
    assert any(isinstance(value, AuditLog) for value in session.added)


@pytest.mark.asyncio
async def test_public_validation_returns_organization_name() -> None:
    user = make_user()
    invitation = make_invitation(user)
    app.dependency_overrides[get_db] = lambda: FakeSession([invitation, "テストクラブ"])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/invitations/code/safe-test-code")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["organization_name"] == "テストクラブ"


@pytest.mark.asyncio
async def test_expired_invitation_is_rejected_and_marked_expired() -> None:
    user = make_user()
    invitation = make_invitation(user, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    session = FakeSession([invitation])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/invitations/code/safe-test-code")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "INVITATION_EXPIRED"
    assert invitation.status == "EXPIRED"
    assert session.committed


@pytest.mark.asyncio
async def test_consume_invitation_increments_use_count() -> None:
    user = make_user()
    invitation = make_invitation(user)
    session = FakeSession([invitation])

    result = await consume_invitation(invitation.invitation_code, session)  # type: ignore[arg-type]

    assert result.used_count == 1
