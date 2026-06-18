"""Authentication and RBAC tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def login(client, email, password):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def test_login_success_and_me(client, seeded, admin_email, admin_password):
    r = await login(client, admin_email, admin_password)
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert "SUPER_ADMIN" in me.json()["roles"]


async def test_login_wrong_password(client, seeded, admin_email):
    r = await login(client, admin_email, "wrong-password")
    assert r.status_code == 401


async def test_admin_endpoint_requires_auth(client, seeded):
    r = await client.post("/api/v1/admin/fixtures/generate", json={})
    assert r.status_code in (401, 422)  # unauthenticated


async def test_change_password_rejects_bad_current(client, seeded, admin_email, admin_password):
    token = (await login(client, admin_email, admin_password)).json()["access_token"]
    r = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "nope", "new_password": "BrandNewPass!99"},
    )
    assert r.status_code == 400
