"""Public WebSocket endpoints for live updates.

Clients connect, optionally subscribe to a fixture room, and receive event
envelopes pushed via Redis. Heartbeats: the server replies to client "ping" text
with a "pong" and tolerates idle connections.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await manager.connect_global(websocket)
    await websocket.send_json({"type": "connection.ready", "payload": {"scope": "live"}})
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        await manager.disconnect(websocket)


@router.websocket("/ws/fixtures/{fixture_id}")
async def ws_fixture(websocket: WebSocket, fixture_id: str) -> None:
    await manager.connect_fixture(websocket, fixture_id)
    await websocket.send_json(
        {"type": "connection.ready", "payload": {"scope": "fixture", "fixture_id": fixture_id}}
    )
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket, fixture_id)
    except Exception:  # noqa: BLE001
        await manager.disconnect(websocket, fixture_id)
