import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import AuditLog, Invitation, InvitationChild
from app.services.invitations import consume_invitation


class Result:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class FakeSession:
    def __init__(
        self,
        scalar_results: list[Any],
        collection_results: list[list[Any]] | None = None,
        rows: list[Any] | None = None,
    ) -> None:
        self.scalar_results = iter(scalar_results)
        self.collection_results = iter(collection_results or [])
        self.rows = rows or []
        self.added: list[Any] = []
        self.committed = False

    async def scalar(self, _: Any) -> Any:
        return next(self.scalar_results)

    async def scalars(self, _: Any) -> Result:
        return Result(next(self.collection_results))

    async def execute(self, _: Any) -> Result:
        return Result(self.rows)

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


def make_child(user: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        first_name="太郎",
        last_name="田中",
        birth_date=date(2019, 4, 1),
        grade="小1",
        status="ACTIVE",
        deleted_at=None,
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
    body = response.json()
    assert body["children"] == []
    invitation = next(value for value in session.added if isinstance(value, Invitation))
    assert invitation.organization_id == user.organization_id
    assert len(invitation.invitation_code) == 32
    assert any(isinstance(value, AuditLog) for value in session.added)


@pytest.mark.asyncio
async def test_create_family_invitation_links_children_and_defaults_guardian_limit() -> None:
    user = make_user()
    child = make_child(user)
    session = FakeSession([user], collection_results=[[child]])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/invitations",
                headers=auth_header(user),
                json={"child_ids": [str(child.id)]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["max_uses"] == 2
    assert [c["id"] for c in body["children"]] == [str(child.id)]
    invitation = next(value for value in session.added if isinstance(value, Invitation))
    assert invitation.max_uses == 2
    link = next(value for value in session.added if isinstance(value, InvitationChild))
    assert link.invitation_id == invitation.id
    assert link.child_id == child.id


@pytest.mark.asyncio
async def test_create_invitation_rejects_unknown_child_id() -> None:
    user = make_user()
    session = FakeSession([user], collection_results=[[]])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/invitations",
                headers=auth_header(user),
                json={"child_ids": [str(uuid.uuid4())]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CHILD_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_invitations_includes_linked_children() -> None:
    user = make_user()
    invitation = make_invitation(user)
    child = make_child(user)
    session = FakeSession(
        [user], collection_results=[[invitation]], rows=[(invitation.id, child)]
    )
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/invitations", headers=auth_header(user))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert [c["id"] for c in body[0]["children"]] == [str(child.id)]


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
    assert response.json()["children"] == []


@pytest.mark.asyncio
async def test_public_validation_includes_family_children() -> None:
    user = make_user()
    invitation = make_invitation(user)
    child = make_child(user)
    session = FakeSession(
        [invitation, "テストクラブ"], rows=[(invitation.id, child)]
    )
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/invitations/code/safe-test-code")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert [c["id"] for c in body["children"]] == [str(child.id)]


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
