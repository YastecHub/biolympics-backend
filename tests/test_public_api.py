"""Integration tests for the public read API against seeded data."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_current_tournament(client, seeded):
    r = await client.get("/api/v1/tournaments/current")
    assert r.status_code == 200
    body = r.json()
    assert body["public_brand"] == "BIOLYMPICS LIVE"
    assert body["slug"] == "deans-games-2026"


async def test_sports_and_departments_seeded(client, seeded):
    sports = (await client.get("/api/v1/sports")).json()
    assert len(sports) == 14
    assert any(s["slug"] == "male-football" for s in sports)

    depts = (await client.get("/api/v1/departments")).json()
    assert len(depts) == 8
    assert any(d["abbreviation"] == "BTN" for d in depts)


async def test_live_fixture_present(client, seeded):
    live = (await client.get("/api/v1/fixtures/live")).json()
    assert len(live) >= 1
    fx = live[0]
    assert fx["live"] is not None
    assert fx["status"] in {"LIVE", "HALF_TIME", "PERIOD_BREAK", "PAUSED"}


async def test_results_and_standings(client, seeded):
    results = (await client.get("/api/v1/results")).json()
    assert len(results) >= 2  # the two completed MD1 fixtures

    standings = (await client.get("/api/v1/standings/male-football")).json()
    assert len(standings) == 2  # Group A and Group B
    group_a = next(s for s in standings if s["group_name"] == "Group A")
    assert len(group_a["rows"]) == 4
    # Winner of BTN 2-1 should sit above the loser.
    assert group_a["rows"][0]["position"] == 1
    # Rows must carry department abbreviations, not raw team ids.
    abbrs = {row["department_abbr"] for row in group_a["rows"]}
    assert abbrs == {"BTN", "CBG", "MSM", "MIC"}
    assert all(row["department_abbr"] for row in group_a["rows"])


async def test_tbd_flags(client, seeded):
    schedule = (await client.get("/api/v1/schedule")).json()
    # Several knockout/Table-Tennis fixtures have no time/venue yet.
    assert any(f["time_tbd"] for f in schedule)
    assert any(f["venue_tbd"] for f in schedule)


async def test_announcements_include_urgent(client, seeded):
    anns = (await client.get("/api/v1/announcements")).json()
    assert any(a["is_urgent"] for a in anns)


async def test_ludo_medals_seeded(client, seeded):
    medals = (await client.get("/api/v1/medal-table")).json()
    podium = {row["department_abbr"]: row for row in medals}

    assert podium["PRE-MED"]["gold"] == 1
    assert podium["PRE-MED"]["total_points"] == 5
    assert podium["CBG"]["silver"] == 1
    assert podium["CBG"]["total_points"] == 2
    assert podium["BCH"]["bronze"] == 1
    assert podium["BCH"]["total_points"] == 1
