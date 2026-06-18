"""Push subscription and notification de-duplication tests."""

from __future__ import annotations

import pytest

from app.db.session import get_sessionmaker
from app.services.notifications import create_event

pytestmark = pytest.mark.asyncio


async def test_subscribe_and_update(client, seeded):
    payload = {
        "endpoint": "https://push.example.com/abc123",
        "keys": {"p256dh": "BPublicKeyValue", "auth": "AuthValue"},
        "preferences": [{"topic": "ALL"}],
        "user_agent": "pytest",
    }
    r = await client.post("/api/v1/push/subscriptions", json=payload)
    assert r.status_code == 201, r.text
    sub_id = r.json()["id"]

    # Re-subscribing the same endpoint upserts rather than duplicating.
    r2 = await client.post("/api/v1/push/subscriptions", json=payload)
    assert r2.status_code == 201
    assert r2.json()["id"] == sub_id

    # Update preferences.
    r3 = await client.patch(
        f"/api/v1/push/subscriptions/{sub_id}",
        json={"preferences": [{"topic": "URGENT_ONLY"}]},
    )
    assert r3.status_code == 200


async def test_public_key_endpoint(client, seeded):
    r = await client.get("/api/v1/push/public-key")
    assert r.status_code == 200
    assert "public_key" in r.json()


async def test_event_dedup_by_idempotency_key(db_setup):
    async with get_sessionmaker()() as db:
        first = await create_event(
            db,
            idempotency_key="goal:fx1:v2",
            event_type="fixture.score_updated",
            title="GOAL",
            body="BCH 1-0 BTN",
        )
        await db.commit()
        second = await create_event(
            db,
            idempotency_key="goal:fx1:v2",
            event_type="fixture.score_updated",
            title="GOAL",
            body="BCH 1-0 BTN",
        )
        assert first is not None
        assert second is None  # duplicate suppressed
