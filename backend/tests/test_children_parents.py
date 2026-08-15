import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import AuditLog, Child


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

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if isinstance(value, Child):
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


def make_child(organization_id: uuid.UUID) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        first_name="太郎",
        last_name="田中",
        first_name_kana="たろう",
        last_name_kana="たなか",
        birth_date=date(2018, 4, 1),
        grade="小2",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


def auth_header(user: SimpleNamespace) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user.id), "organization_id": str(user.organization_id), "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_children_returns_current_tenant_rows() -> None:
    user = make_user()
    child = make_child(user.organization_id)
    app.dependency_overrides[get_db] = lambda: FakeSession([user], [[child]])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/children", headers=auth_header(user))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(child.id)


@pytest.mark.asyncio
async def test_create_child_uses_current_tenant_and_audits() -> None:
    user = make_user()
    session = FakeSession([user])
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/children",
                headers=auth_header(user),
                json={
                    "first_name": "花子",
                    "last_name": "田中",
                    "birth_date": "2019-04-01",
                    "grade": "小1",
                    "status": "ACTIVE",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    child = next(value for value in session.added if isinstance(value, Child))
    audit = next(value for value in session.added if isinstance(value, AuditLog))
    assert child.organization_id == user.organization_id
    assert audit.action == "ADD_CHILD"
    assert session.committed


@pytest.mark.asyncio
async def test_get_child_hides_other_tenant_rows() -> None:
    user = make_user()
    app.dependency_overrides[get_db] = lambda: FakeSession([user, None])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/children/{uuid.uuid4()}", headers=auth_header(user)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_bind_child_rejects_child_outside_current_tenant() -> None:
    user = make_user()
    parent = SimpleNamespace(id=uuid.uuid4(), organization_id=user.organization_id)
    app.dependency_overrides[get_db] = lambda: FakeSession([user, parent, None])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/parents/{parent.id}/children",
                headers=auth_header(user),
                json={"child_id": str(uuid.uuid4())},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
