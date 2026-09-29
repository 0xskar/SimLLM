from __future__ import annotations

from simllm.agents.llm_client import LLMDecision, SummaryResult
from simllm.db import agents_repo, memory_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


async def test_resolved_decision_writes_a_memory(isolated_saves_dir, monkeypatch):
    save_repo.create_save("memwrite", population_target=1)
    conn = save_repo.load_save("memwrite")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(
                action="idle", params={"reason": "Feeling great."}, latency_ms=1.0,
                used_fallback=False, attempts=1,
            )

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        memories = memory_repo.list_all_memories(conn, agent_id)
        assert len(memories) == 1
        assert memories[0]["content"] == "Feeling great."
        assert memories[0]["tick"] == 1
    finally:
        conn.close()


async def test_memory_buffer_included_in_prompt_is_capped(isolated_saves_dir, monkeypatch):
    save_repo.create_save("memcap", population_target=1)
    conn = save_repo.load_save("memcap")
    try:
        settings = save_repo.load_settings(conn)
        settings.memory_buffer_size = 2
        settings.decision_cooldown_ticks = 0  # force due every tick
        save_repo.save_settings(conn, settings)

        captured_messages = []

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            captured_messages.append(messages)
            return LLMDecision(
                action="idle", params={"reason": "content"}, latency_ms=1.0,
                used_fallback=False, attempts=1,
            )

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        for _ in range(4):
            await engine.run_tick()

        last_prompt = captured_messages[-1][1]["content"]
        assert last_prompt.count("- (tick ") == 2  # capped to memory_buffer_size, not all 3 prior
    finally:
        conn.close()


async def test_summarization_updates_life_summary_when_interval_elapses(isolated_saves_dir, monkeypatch):
    save_repo.create_save("summtest", population_target=1)
    conn = save_repo.load_save("summtest")
    try:
        settings = save_repo.load_settings(conn)
        settings.summarization_interval_ticks = 2
        settings.decision_cooldown_ticks = 10
        save_repo.save_settings(conn, settings)

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(action="idle", params={}, latency_ms=1.0, used_fallback=False, attempts=1)

        async def fake_summarize(messages, settings_arg, client=None):
            return SummaryResult(text="Test summary text.", latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)
        monkeypatch.setattr(engine_module, "summarize", fake_summarize)

        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        engine = SimulationEngine(conn, settings, None)

        await engine.run_tick()  # tick 1: interval not yet elapsed (1 < 2)
        assert agents_repo.get_agent_detail(conn, agent_id)["life_summary"] is None

        await engine.run_tick()  # tick 2: interval elapsed
        after = agents_repo.get_agent_detail(conn, agent_id)
        assert after["life_summary"] == "Test summary text."
        assert after["life_summary_updated_tick"] == 2
    finally:
        conn.close()


async def test_failed_summarization_leaves_life_summary_unset(isolated_saves_dir, monkeypatch):
    save_repo.create_save("summfail", population_target=1)
    conn = save_repo.load_save("summfail")
    try:
        settings = save_repo.load_settings(conn)
        settings.summarization_interval_ticks = 1
        save_repo.save_settings(conn, settings)

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(action="idle", params={}, latency_ms=1.0, used_fallback=False, attempts=1)

        async def fake_summarize_fail(messages, settings_arg, client=None):
            return SummaryResult(text=None, latency_ms=0.0, used_fallback=True, attempts=2, error="timeout")

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)
        monkeypatch.setattr(engine_module, "summarize", fake_summarize_fail)

        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        after = agents_repo.get_agent_detail(conn, agent_id)
        assert after["life_summary"] is None
        assert after["life_summary_updated_tick"] is None
    finally:
        conn.close()


async def test_summarization_feeds_memories_since_last_summary(isolated_saves_dir, monkeypatch):
    save_repo.create_save("summfeed", population_target=1)
    conn = save_repo.load_save("summfeed")
    try:
        settings = save_repo.load_settings(conn)
        settings.summarization_interval_ticks = 3
        settings.decision_cooldown_ticks = 0
        save_repo.save_settings(conn, settings)

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

        captured = []

        async def fake_summarize(messages, settings_arg, client=None):
            captured.append(messages)
            return SummaryResult(text="Summary.", latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)
        monkeypatch.setattr(engine_module, "summarize", fake_summarize)

        engine = SimulationEngine(conn, settings, None)
        for _ in range(3):
            await engine.run_tick()

        assert len(captured) == 1
        summary_prompt_content = captured[0][1]["content"]
        assert summary_prompt_content.count("- (tick ") == 3  # all 3 ticks' memories fed in
    finally:
        conn.close()
