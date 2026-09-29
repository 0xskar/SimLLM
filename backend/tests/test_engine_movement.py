from __future__ import annotations

import asyncio

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


def _fake_decide_sequence(actions_and_params):
    """Async decide_action replacement that plays back a scripted sequence
    of (action, params), repeating the last entry, and records call count.

    Side calls that pass a `tools` override (emoji re-pick, relationship
    update, personality generation) are answered generically and don't
    consume the scripted action sequence or its call count -- a fresh
    agent's very first tick always triggers an emoji re-pick (mood jumps
    from the default band to "great" once real needs/health are computed),
    which would otherwise throw off tests that count decisions.
    """
    calls = {"count": 0}
    sequence = list(actions_and_params)

    async def fake(messages, settings, client=None, tools=None):
        if tools is not None:
            return LLMDecision(
                action="idle", params={}, latency_ms=1.0, used_fallback=True, attempts=1, error="unscripted"
            )
        calls["count"] += 1
        action, params = sequence[min(calls["count"] - 1, len(sequence) - 1)]
        return LLMDecision(action=action, params=params, latency_ms=1.0, used_fallback=False, attempts=1)

    fake.calls = calls
    return fake


async def test_move_to_walks_multiple_ticks_without_recalling_llm(isolated_saves_dir, monkeypatch):
    # Note: the seeded world may place a workplace adjacent to the starter
    # house, so the actual path length isn't necessarily the Manhattan
    # distance -- this test only asserts on the behavior that matters:
    # one decision, eventual correct arrival, one agent_moved per step taken.
    save_repo.create_save("movetest", population_target=1, world_width=20, world_height=20)
    conn = save_repo.load_save("movetest")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        start = agents_repo.get_agent_detail(conn, agent_id)
        target = (start["x"] + 3, start["y"])

        fake = _fake_decide_sequence([("move_to", {"target_x": target[0], "target_y": target[1]})])
        monkeypatch.setattr(engine_module, "decide_action", fake)

        moved_events = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "agent_moved":
                moved_events.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)

        for _ in range(20):
            after = agents_repo.get_agent_detail(conn, agent_id)
            if (after["x"], after["y"]) == target:
                break
            await engine.run_tick()
        else:
            raise AssertionError("agent never arrived within 20 ticks")

        # 1 call to start the walk + exactly 1 more immediate redecision on
        # the tick arrival happens (see test_agent_becomes_due_again_immediately_on_arrival).
        assert fake.calls["count"] == 2
        assert moved_events  # movement was actually broadcast
        assert (moved_events[-1]["x"], moved_events[-1]["y"]) == target
    finally:
        conn.close()


async def test_agent_becomes_due_again_immediately_on_arrival(isolated_saves_dir, monkeypatch):
    save_repo.create_save("movetest2", population_target=1, world_width=20, world_height=20)
    conn = save_repo.load_save("movetest2")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        start = agents_repo.get_agent_detail(conn, agent_id)
        target = (start["x"] + 1, start["y"])  # one step away

        fake = _fake_decide_sequence(
            [
                ("move_to", {"target_x": target[0], "target_y": target[1]}),
                ("idle", {"reason": "Arrived."}),
            ]
        )
        monkeypatch.setattr(engine_module, "decide_action", fake)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()  # decides move_to; no step taken yet this tick
        await engine.run_tick()  # steps onto target, arrives, becomes due again this same tick

        after = agents_repo.get_agent_detail(conn, agent_id)
        assert (after["x"], after["y"]) == target
        assert fake.calls["count"] == 2
        assert after["current_goal"] == "Arrived."
    finally:
        conn.close()


async def test_unreachable_move_target_falls_back_to_idle(isolated_saves_dir, monkeypatch):
    save_repo.create_save("movetest3", population_target=1, world_width=20, world_height=20)
    conn = save_repo.load_save("movetest3")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        target = (15, 15)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            conn.execute(
                "UPDATE world_tiles SET tile_type = 'house' WHERE x = ? AND y = ?",
                (target[0] + dx, target[1] + dy),
            )
        conn.commit()

        fake = _fake_decide_sequence([("move_to", {"target_x": target[0], "target_y": target[1]})])
        monkeypatch.setattr(engine_module, "decide_action", fake)

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "unreachable" for log in logs)

        after = agents_repo.get_agent_detail(conn, agent_id)
        assert after["current_action"] is None
    finally:
        conn.close()


async def test_decision_cooldown_skips_llm_calls_until_elapsed(isolated_saves_dir, monkeypatch):
    save_repo.create_save("cooldowntest", population_target=1)
    conn = save_repo.load_save("cooldowntest")
    try:
        settings = save_repo.load_settings(conn)
        settings.decision_cooldown_ticks = 5
        save_repo.save_settings(conn, settings)

        fake = _fake_decide_sequence([("idle", {"reason": "content"})])
        monkeypatch.setattr(engine_module, "decide_action", fake)

        engine = SimulationEngine(conn, settings, None)
        # Tick 1 makes the first (and only, so far) decision, scheduling the
        # next one for tick 1 + cooldown(5) = tick 6.
        for _ in range(5):
            await engine.run_tick()
        assert fake.calls["count"] == 1  # still within cooldown through tick 5

        await engine.run_tick()  # tick 6: cooldown elapsed
        assert fake.calls["count"] == 2
    finally:
        conn.close()


async def test_worker_pool_never_exceeds_configured_concurrency(isolated_saves_dir, monkeypatch):
    save_repo.create_save("pooltest", population_target=6, world_width=16, world_height=16)
    conn = save_repo.load_save("pooltest")
    try:
        settings = save_repo.load_settings(conn)
        settings.worker_concurrency = 2
        save_repo.save_settings(conn, settings)

        state = {"current": 0, "max_seen": 0}

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            state["current"] += 1
            state["max_seen"] = max(state["max_seen"], state["current"])
            await asyncio.sleep(0.02)
            state["current"] -= 1
            return LLMDecision(action="idle", params={}, latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        assert state["max_seen"] <= 2
        assert state["max_seen"] > 1  # real concurrency actually happened, not accidentally serial
    finally:
        conn.close()
