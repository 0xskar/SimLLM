from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


async def test_run_tick_advances_clock_and_sim_time(isolated_saves_dir, monkeypatch):
    async def fake_decide(messages, settings, client=None, tools=None):
        return LLMDecision(action="idle", params={}, latency_ms=1.0, used_fallback=False, attempts=1)

    monkeypatch.setattr(engine_module, "decide_action", fake_decide)

    save_repo.create_save("clocktest", population_target=1)
    conn = save_repo.load_save("clocktest")
    try:
        settings = save_repo.load_settings(conn)
        engine = SimulationEngine(conn, settings)

        before = conn.execute(
            "SELECT current_tick, sim_datetime FROM sim_clock WHERE id = 1"
        ).fetchone()

        result = await engine.run_tick()

        after = conn.execute(
            "SELECT current_tick, sim_datetime FROM sim_clock WHERE id = 1"
        ).fetchone()

        assert after["current_tick"] == before["current_tick"] + 1
        assert result["tick"] == after["current_tick"]
        assert after["sim_datetime"] != before["sim_datetime"]
        assert result["population"] == 1
    finally:
        conn.close()
