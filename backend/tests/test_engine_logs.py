from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import logs_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


async def test_resolved_decision_persists_to_events_log(isolated_saves_dir, monkeypatch):
    save_repo.create_save("enginelogtest", population_target=1)
    conn = save_repo.load_save("enginelogtest")
    try:
        settings = save_repo.load_settings(conn)

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(
                action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1
            )

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        events = logs_repo.list_events(conn, category="llm_call")
        assert len(events) == 1
        assert events[0]["agent_id"] == 1
        assert events[0]["tick"] == 1
    finally:
        conn.close()
