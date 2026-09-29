from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(
        self,
        event_type: str,
        payload: dict,
        tick: int | None = None,
        sim_time: str | None = None,
    ) -> None:
        message = {
            "type": event_type,
            "tick": tick,
            "sim_time": sim_time,
            "payload": payload,
        }
        text = json.dumps(message)
        dead: list[WebSocket] = []
        for websocket in self.active:
            try:
                await websocket.send_text(text)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Clients don't need to send anything; just keep the socket open
            # and drain any incoming frames (e.g. browser pings).
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
