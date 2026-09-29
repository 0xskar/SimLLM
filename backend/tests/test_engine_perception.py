from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


async def test_prompt_only_includes_agents_within_perception_radius(isolated_saves_dir, monkeypatch):
    save_repo.create_save("percep", population_target=3, world_width=20, world_height=20)
    conn = save_repo.load_save("percep")
    try:
        settings = save_repo.load_settings(conn)
        settings.perception_radius = 3
        save_repo.save_settings(conn, settings)

        agents = agents_repo.list_agent_summaries(conn)
        a_id, b_id, c_id = agents[0]["id"], agents[1]["id"], agents[2]["id"]
        a_name, b_name, c_name = agents[0]["name"], agents[1]["name"], agents[2]["name"]

        conn.execute("UPDATE agents SET x = 0, y = 0 WHERE id = ?", (a_id,))
        conn.execute("UPDATE agents SET x = 2, y = 0 WHERE id = ?", (b_id,))  # within radius 3
        conn.execute("UPDATE agents SET x = 15, y = 15 WHERE id = ?", (c_id,))  # far outside
        conn.commit()

        captured = {}

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            if tools is None:
                content = messages[1]["content"]
                if content.startswith(f"You are {a_name} "):
                    captured["a_prompt"] = content
            return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        content = captured["a_prompt"]
        assert b_name in content
        assert c_name not in content
    finally:
        conn.close()


async def test_perception_uses_post_movement_position_for_due_agent_this_tick(isolated_saves_dir, monkeypatch):
    # An agent that arrives (movement completes) and becomes due again in the
    # SAME tick hasn't had its new position persisted to the DB yet -- make
    # sure perception for OTHER agents still sees its up-to-date position,
    # not the stale pre-arrival one.
    save_repo.create_save("percep2", population_target=2, world_width=20, world_height=20)
    conn = save_repo.load_save("percep2")
    try:
        settings = save_repo.load_settings(conn)
        settings.perception_radius = 2
        save_repo.save_settings(conn, settings)

        agents = agents_repo.list_agent_summaries(conn)
        mover_id, observer_id = agents[0]["id"], agents[1]["id"]
        mover_name, observer_name = agents[0]["name"], agents[1]["name"]

        # Mover is mid-path, about to take its final step onto (2, 0) this tick.
        import json

        conn.execute(
            "UPDATE agents SET x = 1, y = 0, current_action = ?, next_decision_tick = 1 WHERE id = ?",
            (json.dumps({"type": "move_to", "path": [[2, 0]], "target": [2, 0]}), mover_id),
        )
        conn.execute("UPDATE agents SET x = 2, y = 0 WHERE id = ?", (observer_id,))
        conn.commit()

        captured = {}

        async def fake_decide(messages, settings_arg, client=None, tools=None):
            if tools is None:
                content = messages[1]["content"]
                if content.startswith(f"You are {observer_name} "):
                    captured["observer_prompt"] = content
            return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        # Mover ends this tick at (2, 0), same tile as observer -- well within
        # radius 2, so the observer's prompt should mention the mover even
        # though the mover's DB row hadn't been written yet when perception
        # was computed.
        assert mover_name in captured["observer_prompt"]
    finally:
        conn.close()
