"""The default (lean) seed loads real structure only — no mocked match data."""

from __future__ import annotations

import pytest

from app.db.session import get_sessionmaker
from app.seeds.seed import seed

pytestmark = pytest.mark.asyncio


async def test_lean_seed_has_no_mocked_results(client):
    async with get_sessionmaker()() as db:
        summary = await seed(db, with_demo=False)
    assert summary["mode"] == "live"
    assert summary["fixtures"] > 0

    fixtures = (await client.get("/api/v1/schedule")).json()
    assert len(fixtures) > 0
    # Nothing has been played or recorded yet.
    assert all(f["live"] is None for f in fixtures)
    assert all(f["status"] not in {"LIVE", "COMPLETED", "WALKOVER"} for f in fixtures)

    assert (await client.get("/api/v1/fixtures/live")).json() == []
    assert (await client.get("/api/v1/results")).json() == []
    # Sample content is not seeded in live mode.
    assert (await client.get("/api/v1/announcements")).json() == []
    assert (await client.get("/api/v1/sponsors")).json() == []


async def test_lean_seed_keeps_real_structure(client):
    async with get_sessionmaker()() as db:
        await seed(db, with_demo=False)
    assert len((await client.get("/api/v1/sports")).json()) == 14
    assert len((await client.get("/api/v1/departments")).json()) == 8
    # Group tables exist but every team has played zero matches.
    standings = (await client.get("/api/v1/standings/male-football")).json()
    assert len(standings) == 2
    assert all(row["played"] == 0 for s in standings for row in s["rows"])


async def test_lean_seed_creates_super_admin(client, admin_email, admin_password):
    async with get_sessionmaker()() as db:
        await seed(db, with_demo=False)
    login = await client.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": admin_password}
    )
    assert login.status_code == 200, login.text
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert "SUPER_ADMIN" in me.json()["roles"]
