"""
A minimal WebSocket fan-out so every connected dashboard sees the same
live stream of events, entity updates, decisions and metrics snapshots.
One broadcast -> every connected client, no per-client filtering needed
for a project this size.
"""
from __future__ import annotations

import json

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message_type: str, data) -> None:
        if not self._connections:
            return
        payload = json.dumps({"type": message_type, "data": data}, default=str)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
