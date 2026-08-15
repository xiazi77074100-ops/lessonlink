import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import decode_access_token, hash_password
from app.db.session import get_db
from app.main import app


class FakeSession:
    def __init__(self, result: Any) -> None:
        self.result = result

    async def scalar(self, _: Any) -> Any:
        return self.result


def make_admin() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="admin@example.com",
        password_hash=hash_password("password123"),
        display_name="管理者",
        role="OWNER",
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_login_returns_admin_jwt() -> None:
    user = make_admin()
    app.dependency_overrides[get_db] = lambda: FakeSession(user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "ADMIN@example.com", "password": "password123"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    claims = decode_access_token(response.json()["access_token"])
    assert claims["sub"] == str(user.id)
    assert claims["admin_user_id"] == str(user.id)
    assert claims["organization_id"] == str(user.organization_id)
    assert claims["role"] == "OWNER"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password() -> None:
    app.dependency_overrides[get_db] = lambda: FakeSession(make_admin())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.com", "password": "wrong"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_me_returns_authenticated_admin() -> None:
    user = make_admin()
    app.dependency_overrides[get_db] = lambda: FakeSession(user)
    from app.core.security import create_access_token

    token = create_access_token(
        {"sub": str(user.id), "organization_id": str(user.organization_id), "role": user.role}
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert response.json()["organization_id"] == str(user.organization_id)


@pytest.mark.asyncio
async def test_me_requires_valid_bearer_token() -> None:
    app.dependency_overrides[get_db] = lambda: FakeSession(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            missing = await client.get("/api/v1/me")
            invalid = await client.get(
                "/api/v1/me", headers={"Authorization": "Bearer invalid-token"}
            )
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHORIZED"
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_TOKEN"
