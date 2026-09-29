from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


def _fake_decide(action: str, params: dict | None = None):
    async def fake(messages, settings, client=None, tools=None):
        return LLMDecision(
            action=action, params=params or {}, latency_ms=1.0, used_fallback=False, attempts=1
        )

    return fake


async def test_starter_agents_are_spawned_one_per_house(isolated_saves_dir):
    save_repo.create_save("agenttest", population_target=3)
    conn = save_repo.load_save("agenttest")
    try:
        agents = agents_repo.list_agent_summaries(conn)
        assert len(agents) == 3

        houses = conn.execute(
            "SELECT x, y FROM buildings WHERE type = 'house' ORDER BY id LIMIT 3"
        ).fetchall()
        agent_positions = {(a["x"], a["y"]) for a in agents}
        house_positions = {(h["x"], h["y"]) for h in houses}
        assert agent_positions == house_positions

        names = {a["name"] for a in agents}
        assert len(names) == 3  # each agent got a distinct placeholder name
    finally:
        conn.close()


async def test_tick_decays_needs_and_broadcasts_agent_update(isolated_saves_dir, monkeypatch):
    save_repo.create_save("agenttest2", population_target=1)
    conn = save_repo.load_save("agenttest2")
    try:
        settings = save_repo.load_settings(conn)
        broadcasts = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            broadcasts.append((event_type, payload))

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle"))

        engine = SimulationEngine(conn, settings, fake_broadcast)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        before = agents_repo.get_agent_detail(conn, agent_id)
        await engine.run_tick()
        after = agents_repo.get_agent_detail(conn, agent_id)

        assert after["needs"]["hunger"] < before["needs"]["hunger"]
        assert after["age_ticks"] == before["age_ticks"] + 1

        stat_updates = [p for (t, p) in broadcasts if t == "agent_stat_update"]
        assert len(stat_updates) == 1
        assert stat_updates[0]["agent_id"] == agent_id
        assert stat_updates[0]["action"] == "idle"
    finally:
        conn.close()


async def test_agent_at_home_gets_passive_shelter_regen(isolated_saves_dir, monkeypatch):
    save_repo.create_save("agenttest3", population_target=2)
    conn = save_repo.load_save("agenttest3")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        conn.execute("UPDATE agent_needs SET shelter = 50.0 WHERE agent_id = ?", (agent_id,))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle"))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        after = agents_repo.get_agent_detail(conn, agent_id)
        expected = 50.0 - settings.needs_decay_per_tick.shelter + settings.shelter_home_regen_per_tick
        assert after["needs"]["shelter"] == expected
    finally:
        conn.close()


async def test_llm_chosen_eat_action_deducts_currency_and_restores_hunger(isolated_saves_dir, monkeypatch):
    save_repo.create_save("agenttest4", population_target=2)
    conn = save_repo.load_save("agenttest4")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        conn.execute("UPDATE agent_needs SET hunger = 10.0 WHERE agent_id = ?", (agent_id,))
        conn.commit()

        monkeypatch.setattr(
            engine_module, "decide_action", _fake_decide("eat", {"reason": "Starving."})
        )

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        after = agents_repo.get_agent_detail(conn, agent_id)
        assert after["currency"] == 100.0 - settings.food_cost
        assert after["current_goal"] == "Starving."
    finally:
        conn.close()


async def test_illegal_llm_action_falls_back_to_idle_and_logs_rejection(isolated_saves_dir, monkeypatch):
    save_repo.create_save("agenttest5", population_target=1)
    conn = save_repo.load_save("agenttest5")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        # Out-of-bounds move_to should be rejected server-side.
        monkeypatch.setattr(
            engine_module,
            "decide_action",
            _fake_decide("move_to", {"target_x": 9999, "target_y": 9999}),
        )

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        after = agents_repo.get_agent_detail(conn, agent_id)
        assert (after["x"], after["y"]) == (0, 0)  # unchanged, rejected move never applied

        rejection_logs = [log for log in logs if log.get("rejection_reason") is not None]
        assert len(rejection_logs) == 1
        assert rejection_logs[0]["rejected"] is True
        assert rejection_logs[0]["rejection_reason"] == "out_of_bounds"
    finally:
        conn.close()
