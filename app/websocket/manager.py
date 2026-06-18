"""In-process WebSocket connection manager.

Tracks the global "live" feed and optional per-fixture subscriptions. Delivery is
best-effort; dead sockets are pruned. Cross-instance fan-out is handled by the
Redis subscriber in app.services.events.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from starlette.websockets import WebSocket, WebSocketState

log = structlog.get_logger("ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._global: set[WebSocket] = set()
        self._by_fixture: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._global) + sum(len(s) for s in self._by_fixture.values())

    async def connect_global(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._global.add(ws)
        log.info("ws.connect", scope="global", total=self.connection_count)

    async def connect_fixture(self, ws: WebSocket, fixture_id: str) -> None:
        await ws.accept()
        async with self._lock:
            self._by_fixture.setdefault(fixture_id, set()).add(ws)
        log.info("ws.connect", scope="fixture", fixture_id=fixture_id)

    async def disconnect(self, ws: WebSocket, fixture_id: str | None = None) -> None:
        async with self._lock:
            self._global.discard(ws)
            if fixture_id and fixture_id in self._by_fixture:
                self._by_fixture[fixture_id].discard(ws)
                if not self._by_fixture[fixture_id]:
                    del self._by_fixture[fixture_id]

    async def _send(self, ws: WebSocket, message: dict[str, Any]) -> bool:
        if ws.application_state != WebSocketState.CONNECTED:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:  # noqa: BLE001 — client vanished
            return False

    async def broadcast(self, envelope: dict[str, Any]) -> None:
        """Send to all global subscribers and to the relevant fixture room."""
        fixture_id = envelope.get("fixture_id")
        targets: set[WebSocket] = set(self._global)
        if fixture_id and fixture_id in self._by_fixture:
            targets |= self._by_fixture[fixture_id]

        dead: list[WebSocket] = []
        for ws in targets:
            if not await self._send(ws, envelope):
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, fixture_id)


manager = ConnectionManager()
