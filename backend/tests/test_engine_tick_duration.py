from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


async def test_run_tick_reports_and_logs_duration(isolated_saves_dir, monkeypatch):
    async def fake_decide(messages, settings, client=None, tools=None):
        return LLMDecision(action="idle", params={}, latency_ms=1.0, used_fallback=False, attempts=1)

    monkeypatch.setattr(engine_module, "decide_action", fake_decide)

    save_repo.create_save("tickdurationtest", population_target=1)
    conn = save_repo.load_save("tickdurationtest")
    try:
        settings = save_repo.load_settings(conn)

        system_logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log" and payload.get("category") == "system":
                system_logs.append(payload["message"])

        engine = SimulationEngine(conn, settings, fake_broadcast)
        result = await engine.run_tick()

        assert isinstance(result["tick_duration_ms"], float)
        assert result["tick_duration_ms"] >= 0.0
        assert any("took" in m and "ms" in m for m in system_logs)
    finally:
        conn.close()
