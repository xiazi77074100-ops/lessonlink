import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, decode_access_token
from app.db.session import get_db
from app.main import app
from app.models import AdminUser, Organization


class FakeSession:
    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = iter(results or [])
        self.added: list[Any] = []
        self.committed = False

    async def scalar(self, _: Any) -> Any:
        return next(self.results)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if isinstance(value, Organization):
                value.plan = "free"
                value.created_at = now
                value.updated_at = now

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    async def refresh(self, _: Any) -> None:
        pass


def make_user(role: str = "OWNER") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), role=role, deleted_at=None
    )


def make_organization(organization_id: uuid.UUID) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=organization_id,
        name="テストクラブ",
        organization_type="サッカー",
        address=None,
        phone=None,
        email="club@example.com",
        plan="free",
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
async def test_create_organization_creates_owner_and_returns_token() -> None:
    session = FakeSession()
    app.dependency_overrides[get_db] = lambda: session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/organizations",
                json={
                    "name": "新しいクラブ",
                    "organization_type": "サッカー",
                    "address": None,
                    "phone": None,
                    "email": "club@example.com",
                    "owner_email": "owner@example.com",
                    "owner_password": "password123",
                    "owner_display_name": "オーナー",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert session.committed
    owner = next(value for value in session.added if isinstance(value, AdminUser))
    organization = next(value for value in session.added if isinstance(value, Organization))
    assert owner.organization_id == organization.id
    claims = decode_access_token(response.json()["access_token"])
    assert claims["organization_id"] == str(organization.id)


@pytest.mark.asyncio
async def test_get_organizations_only_returns_current_tenant() -> None:
    user = make_user()
    organization = make_organization(user.organization_id)
    app.dependency_overrides[get_db] = lambda: FakeSession([user, organization])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/organizations", headers=auth_header(user))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(user.organization_id)


@pytest.mark.asyncio
async def test_update_organization_rejects_cross_tenant_id() -> None:
    user = make_user()
    app.dependency_overrides[get_db] = lambda: FakeSession([user])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/organizations/{uuid.uuid4()}",
                headers=auth_header(user),
                json={"name": "変更", "organization_type": "野球"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_staff_cannot_update_organization() -> None:
    user = make_user(role="STAFF")
    app.dependency_overrides[get_db] = lambda: FakeSession([user])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/api/v1/organizations/{user.organization_id}",
                headers=auth_header(user),
                json={"name": "変更", "organization_type": "野球"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
