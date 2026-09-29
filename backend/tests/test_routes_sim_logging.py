from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.agents.llm_client import LLMDecision
from simllm.db import save_repo
from simllm.main import app
from simllm.sim import engine as engine_module


def test_pause_logs_a_system_event(isolated_saves_dir, monkeypatch):
    # Only exercises pause (never start/resume) so the sim clock's background
    # tick loop never actually spins up -- no risk of a real LLM call
    # racing this test.
    save_repo.create_save("simlogtest", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simlogtest/load")

    response = client.post("/api/sim/pause")
    assert response.status_code == 200

    logs_response = client.get("/api/logs", params={"category": "system"})
    messages = [e["message"] for e in logs_response.json()]
    assert any("paused" in m for m in messages)


def test_start_and_pause_log_system_events(isolated_saves_dir, monkeypatch):
    # Starting the sim does spin up the background tick loop, so make the
    # main decision call fast/fake to keep this test deterministic and quick.
    async def fake_decide(messages, settings, client=None, tools=None):
        return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

    monkeypatch.setattr(engine_module, "decide_action", fake_decide)

    save_repo.create_save("simlogtest2", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simlogtest2/load")

    client.post("/api/sim/start")
    client.post("/api/sim/pause")

    logs_response = client.get("/api/logs", params={"category": "system"})
    messages = [e["message"] for e in logs_response.json()]
    assert any("started" in m for m in messages)
    assert any("paused" in m for m in messages)


def test_save_load_logs_a_system_event(isolated_saves_dir):
    save_repo.create_save("simlogtest3", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simlogtest3/load")

    logs_response = client.get("/api/logs", params={"category": "system"})
    messages = [e["message"] for e in logs_response.json()]
    assert any("loaded" in m for m in messages)


def test_pause_sets_last_saved_at(isolated_saves_dir):
    save_repo.create_save("simlogtest4", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simlogtest4/load")

    before = client.get("/api/sim/status").json()
    assert before["last_saved_at"] is None

    client.post("/api/sim/pause")

    after = client.get("/api/sim/status").json()
    assert after["last_saved_at"] is not None

    saves_response = client.get("/api/saves").json()
    simlogtest4 = next(s for s in saves_response if s["name"] == "simlogtest4")
    assert simlogtest4["last_saved_at"] == after["last_saved_at"]
