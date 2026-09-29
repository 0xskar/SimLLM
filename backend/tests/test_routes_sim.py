from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.agents.llm_client import LLMDecision
from simllm.db import save_repo
from simllm.main import app
from simllm.sim import engine as engine_module
from simllm.state import app_state


def _fake_decide_idle(monkeypatch):
    async def fake_decide(messages, settings, client=None, tools=None):
        return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

    monkeypatch.setattr(engine_module, "decide_action", fake_decide)


def test_step_advances_one_tick_while_paused(isolated_saves_dir, monkeypatch):
    _fake_decide_idle(monkeypatch)
    save_repo.create_save("simroutestep", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simroutestep/load")

    before = client.get("/api/sim/status").json()
    assert before["is_paused"] is True

    response = client.post("/api/sim/step")
    assert response.status_code == 200
    assert response.json()["tick"] == before["tick"] + 1


def test_step_rejected_while_running(isolated_saves_dir, monkeypatch):
    _fake_decide_idle(monkeypatch)
    save_repo.create_save("simroutestepreject", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simroutestepreject/load")

    client.post("/api/sim/start")
    response = client.post("/api/sim/step")
    assert response.status_code == 400

    client.post("/api/sim/pause")


def test_resume_unpauses_and_logs(isolated_saves_dir, monkeypatch):
    _fake_decide_idle(monkeypatch)
    save_repo.create_save("simrouteresume", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/simrouteresume/load")

    client.post("/api/sim/pause")
    response = client.post("/api/sim/resume")
    assert response.status_code == 200
    assert response.json()["is_paused"] is False

    logs = client.get("/api/logs", params={"category": "system"}).json()
    assert any("resumed" in e["message"] for e in logs)

    client.post("/api/sim/pause")


def test_sim_routes_400_when_no_save_loaded(monkeypatch):
    monkeypatch.setattr(app_state, "clock", None)
    client = TestClient(app)

    response = client.post("/api/sim/step")
    assert response.status_code == 400
