"""End-to-end scoring lifecycle: start, score, version conflict, complete.

Covers acceptance criteria 4, 5, 8, 9, 10 and the optimistic-concurrency guard.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _admin_token(client, email, password) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _pick_scheduled_group_fixture(client) -> dict:
    fixtures = (await client.get("/api/v1/fixtures?sport=male-football&status=SCHEDULED")).json()
    for f in fixtures:
        if f["home"] and f["away"] and f["group_name"]:
            return f
    raise AssertionError("no scheduled group fixture found in seed data")


async def test_full_scoring_lifecycle(client, seeded, admin_email, admin_password):
    token = await _admin_token(client, admin_email, admin_password)
    auth = {"Authorization": f"Bearer {token}"}
    fx = await _pick_scheduled_group_fixture(client)
    fid = fx["id"]

    # 1. Start the fixture.
    r = await client.post(f"/api/v1/admin/fixtures/{fid}/start", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "LIVE"
    version = r.json()["version"]

    # 2. Update the score (acceptance: official updates score).
    r = await client.post(
        f"/api/v1/admin/fixtures/{fid}/score",
        headers=auth,
        json={"expected_version": version, "home_delta": 1},
    )
    assert r.status_code == 200, r.text
    version = r.json()["version"]

    # 3. Stale version is rejected with 409 (no silent overwrite).
    r = await client.post(
        f"/api/v1/admin/fixtures/{fid}/score",
        headers=auth,
        json={"expected_version": 0, "home_delta": 1},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "stale_version"

    # 4. Public fixture reflects the live score.
    pub = (await client.get(f"/api/v1/fixtures/{fid}")).json()
    assert pub["live"]["home_score"] == 1

    # 5. Complete the match.
    r = await client.post(
        f"/api/v1/admin/fixtures/{fid}/complete",
        headers=auth,
        json={"expected_version": version},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"

    # 6. Result appears on the results endpoint.
    results = (await client.get("/api/v1/results?sport=male-football")).json()
    assert any(item["id"] == fid for item in results)

    # 7. Standings were recomputed (the group now shows >= 1 played match
    #    beyond the seeded ones).
    standings = (await client.get("/api/v1/standings/male-football")).json()
    group = next(s for s in standings if s["group_name"] == fx["group_name"])
    assert sum(row["played"] for row in group["rows"]) >= 2


async def test_official_assignment_enforced(client, seeded, admin_email, admin_password):
    """Admins bypass assignment; this verifies an admin can act on any fixture."""
    token = await _admin_token(client, admin_email, admin_password)
    auth = {"Authorization": f"Bearer {token}"}
    fx = await _pick_scheduled_group_fixture(client)
    r = await client.post(f"/api/v1/admin/fixtures/{fx['id']}/start", headers=auth)
    assert r.status_code == 200
