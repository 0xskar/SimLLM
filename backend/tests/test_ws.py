from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.api.ws import ConnectionManager
from simllm.db import save_repo
from simllm.main import app


class _FakeWebSocket:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list[str] = []

    async def accept(self) -> None:
        pass

    async def send_text(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("connection reset")
        self.sent.append(text)


async def test_connect_adds_and_disconnect_removes_socket():
    manager = ConnectionManager()
    ws = _FakeWebSocket()

    await manager.connect(ws)
    assert ws in manager.active

    manager.disconnect(ws)
    assert ws not in manager.active

    # Disconnecting something never connected is a no-op, not an error.
    manager.disconnect(ws)


async def test_broadcast_sends_to_all_active_sockets():
    manager = ConnectionManager()
    a, b = _FakeWebSocket(), _FakeWebSocket()
    await manager.connect(a)
    await manager.connect(b)

    await manager.broadcast("tick_complete", {"tick": 1}, tick=1, sim_time="t1")

    assert len(a.sent) == 1
    assert len(b.sent) == 1
    assert '"type": "tick_complete"' in a.sent[0]


async def test_broadcast_drops_sockets_that_fail_to_send():
    manager = ConnectionManager()
    healthy, broken = _FakeWebSocket(), _FakeWebSocket(fail=True)
    await manager.connect(healthy)
    await manager.connect(broken)

    await manager.broadcast("log", {"message": "hi"})

    assert broken not in manager.active
    assert healthy in manager.active
    assert len(healthy.sent) == 1


def test_websocket_endpoint_receives_broadcast_events(isolated_saves_dir):
    save_repo.create_save("wsroutetest", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/wsroutetest/load")

    with client.websocket_connect("/ws") as websocket:
        client.post("/api/sim/pause")
        message = websocket.receive_json()

    assert message["type"] == "log"
    assert "paused" in message["payload"]["message"]
