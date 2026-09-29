from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


async def test_autosave_fires_only_at_the_configured_interval(isolated_saves_dir, monkeypatch):
    save_repo.create_save("autosaveengine", population_target=1)
    conn = save_repo.load_save("autosaveengine")
    try:
        settings = save_repo.load_settings(conn)
        settings.autosave_interval_ticks = 3
        save_repo.save_settings(conn, settings)

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        system_logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log" and payload.get("category") == "system":
                system_logs.append((tick, payload["message"]))

        engine = SimulationEngine(conn, settings, fake_broadcast)

        await engine.run_tick()  # tick 1
        assert save_repo.list_saves()[0].last_saved_at is None
        await engine.run_tick()  # tick 2
        assert save_repo.list_saves()[0].last_saved_at is None
        await engine.run_tick()  # tick 3 -> autosave

        last_saved = save_repo.list_saves()[0].last_saved_at
        assert last_saved is not None
        assert any("Autosaved at tick 3" in msg for _, msg in system_logs)
    finally:
        conn.close()


async def test_autosave_disabled_when_interval_is_zero(isolated_saves_dir, monkeypatch):
    save_repo.create_save("autosavedisabled", population_target=1)
    conn = save_repo.load_save("autosavedisabled")
    try:
        settings = save_repo.load_settings(conn)
        settings.autosave_interval_ticks = 0
        save_repo.save_settings(conn, settings)

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        for _ in range(5):
            await engine.run_tick()

        assert save_repo.list_saves()[0].last_saved_at is None
    finally:
        conn.close()
