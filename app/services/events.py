"""WebSocket event envelopes and the Redis-backed event bus.

Flow: a write handler calls ``publish_event(...)`` which pushes a JSON envelope
onto a Redis pub/sub channel. Each backend instance runs one subscriber that
fans the message out to its locally-connected WebSocket clients, so horizontal
scaling stays consistent. When Redis is unavailable (e.g. unit tests) the bus
falls back to delivering directly to local clients.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
import structlog

from app.core.config import settings
from app.websocket.manager import manager

log = structlog.get_logger("events")

LIVE_CHANNEL = "biolympics:live"

# Canonical event types (also documented in docs/notification-flow.md).
EVENT_TYPES = {
    "fixture.started",
    "fixture.score_updated",
    "fixture.period_updated",
    "fixture.event_added",
    "fixture.paused",
    "fixture.resumed",
    "fixture.completed",
    "fixture.postponed",
    "fixture.cancelled",
    "fixture.corrected",
    "announcement.published",
    "schedule.changed",
    "standings.updated",
    "medal_table.updated",
}


def _json_default(obj: Any) -> Any:
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.astimezone(UTC).isoformat()
    raise TypeError(f"Cannot serialize {type(obj)}")


def build_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    fixture_id: uuid.UUID | str | None = None,
    sport: str | None = None,
    version: int | None = None,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "event_id": str(uuid.uuid4()),
        "fixture_id": str(fixture_id) if fixture_id else None,
        "sport": sport,
        "timestamp": datetime.now(UTC).isoformat(),
        "version": version,
        "payload": payload,
    }


class EventBus:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._use_redis = False

    async def connect(self) -> None:
        try:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            self._use_redis = True
            log.info("event_bus.redis_connected", url=settings.redis_url)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully without Redis
            self._use_redis = False
            log.warning("event_bus.redis_unavailable", error=str(exc))

    async def publish(self, envelope: dict[str, Any]) -> None:
        data = json.dumps(envelope, default=_json_default)
        if self._use_redis and self._redis is not None:
            try:
                await self._redis.publish(LIVE_CHANNEL, data)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("event_bus.publish_failed", error=str(exc))
        # Fallback: deliver to this instance's clients directly.
        await manager.broadcast(envelope)

    async def run_subscriber(self) -> None:
        """Long-running task: relay Redis messages to local WebSocket clients."""
        if not (self._use_redis and self._redis is not None):
            return
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(LIVE_CHANNEL)
        log.info("event_bus.subscriber_started", channel=LIVE_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(message["data"])
                except (ValueError, KeyError):
                    continue
                await manager.broadcast(envelope)
        finally:
            await pubsub.unsubscribe(LIVE_CHANNEL)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()


bus = EventBus()


async def publish_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    fixture_id: uuid.UUID | str | None = None,
    sport: str | None = None,
    version: int | None = None,
) -> dict[str, Any]:
    envelope = build_envelope(
        event_type, payload, fixture_id=fixture_id, sport=sport, version=version
    )
    await bus.publish(envelope)
    return envelope
