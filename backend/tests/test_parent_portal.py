import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, decode_access_token
from app.db.session import get_db
from app.main import app
from app.models import AuditLog, Parent, ParentChild
from app.services.line_auth import LineIdentity


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
            if isinstance(value, Parent):
                value.created_at = now
                value.updated_at = now

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _: Any) -> None:
        pass


def make_invitation() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        invitation_code="valid-invitation",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        max_uses=10,
        used_count=0,
        status="ACTIVE",
    )


def make_parent(organization_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        line_user_id="U-test-user",
        display_name="田中さん",
        deleted_at=None,
    )


def parent_header(parent: SimpleNamespace) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": str(parent.id),
            "organization_id": str(parent.organization_id),
            "token_type": "parent",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_line_login_creates_parent_and_consumes_invitation_once(monkeypatch: Any) -> None:
    invitation = make_invitation()
    session = FakeSession([invitation, None])

    async def verify(_: str) -> LineIdentity:
        return LineIdentity("U-test-user", "田中さん")

    monkeypatch.setattr("app.api.v1.parent_portal.verify_line_id_token", verify)
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/parent/auth/line",
                json={"id_token": "real-looking-token", "invitation_code": "valid-invitation"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert invitation.used_count == 1
    parent = next(value for value in session.added if isinstance(value, Parent))
    assert parent.organization_id == invitation.organization_id
    claims = decode_access_token(response.json()["access_token"])
    assert claims["token_type"] == "parent"
    assert any(
        isinstance(value, AuditLog) and value.action == "PARENT_JOINED"
        for value in session.added
    )


@pytest.mark.asyncio
async def test_repeat_line_login_does_not_consume_invitation(monkeypatch: Any) -> None:
    invitation = make_invitation()
    parent = make_parent(invitation.organization_id)
    session = FakeSession([invitation, parent])

    async def verify(_: str) -> LineIdentity:
        return LineIdentity(parent.line_user_id, parent.display_name)

    monkeypatch.setattr("app.api.v1.parent_portal.verify_line_id_token", verify)
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/parent/auth/line",
                json={"id_token": "real-looking-token", "invitation_code": "valid-invitation"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert invitation.used_count == 0


@pytest.mark.asyncio
async def test_bind_child_requires_matching_birth_date_and_audits_failure() -> None:
    parent = make_parent()
    child = SimpleNamespace(
        id=uuid.uuid4(), organization_id=parent.organization_id, birth_date=date(2018, 4, 1)
    )
    session = FakeSession([parent, child])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/parent/children/bind",
                headers=parent_header(parent),
                json={"child_id": str(child.id), "birth_date": "2018-05-01"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CHILD_VERIFICATION_FAILED"
    assert any(
        isinstance(value, AuditLog) and value.action == "CHILD_BIND_FAILED"
        for value in session.added
    )


@pytest.mark.asyncio
async def test_bind_child_creates_verified_relationship() -> None:
    parent = make_parent()
    child = SimpleNamespace(
        id=uuid.uuid4(), organization_id=parent.organization_id, birth_date=date(2018, 4, 1)
    )
    session = FakeSession([parent, child, None])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/parent/children/bind",
                headers=parent_header(parent),
                json={"child_id": str(child.id), "birth_date": "2018-04-01"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    binding = next(value for value in session.added if isinstance(value, ParentChild))
    assert binding.organization_id == parent.organization_id
    assert binding.verified_at is not None


@pytest.mark.asyncio
async def test_parent_cannot_answer_for_unbound_child() -> None:
    parent = make_parent()
    event = SimpleNamespace(id=uuid.uuid4(), organization_id=parent.organization_id)
    session = FakeSession([parent, event, None])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/parent/attendance",
                headers=parent_header(parent),
                json={
                    "event_id": str(event.id),
                    "child_id": str(uuid.uuid4()),
                    "status": "ATTENDING",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
