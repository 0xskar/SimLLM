from __future__ import annotations

from simllm.agents.llm_client import LLMDecision, SummaryResult
from simllm.db import agents_repo, memory_repo, relationships_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


def _router_decide(action_by_name: dict, relationship_decision=None):
    """Fake decide_action that scripts a response per agent (matched by the
    'You are {name} ' prefix every prompt starts with), and separately
    handles the relationship-update call (identified by a non-None `tools`
    override, since that's the only caller that passes one)."""

    async def fake(messages, settings, client=None, tools=None):
        if tools is not None:
            if relationship_decision is not None:
                return relationship_decision
            return LLMDecision(
                action="idle", params={}, latency_ms=1.0, used_fallback=True, attempts=1, error="unconfigured"
            )
        content = messages[1]["content"]
        for name, (action, params) in action_by_name.items():
            if content.startswith(f"You are {name} "):
                return LLMDecision(action=action, params=dict(params), latency_ms=1.0, used_fallback=False, attempts=1)
        raise AssertionError(f"unscripted prompt: {content[:150]}")

    return fake


def _fake_reply(reply_text: str = "Hi there!"):
    async def fake(messages, settings, client=None, max_chars=None):
        return SummaryResult(text=reply_text, latency_ms=1.0, used_fallback=False, attempts=1)

    return fake


async def test_successful_conversation_updates_both_agents_and_relationship(isolated_saves_dir, monkeypatch):
    save_repo.create_save("convtest", population_target=2, world_width=10, world_height=10)
    conn = save_repo.load_save("convtest")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        a_id, b_id = agents[0]["id"], agents[1]["id"]
        a_name, b_name = agents[0]["name"], agents[1]["name"]
        conn.execute("UPDATE agents SET x = 0, y = 0 WHERE id = ?", (a_id,))
        conn.execute("UPDATE agents SET x = 1, y = 0 WHERE id = ?", (b_id,))
        conn.commit()

        rel_decision = LLMDecision(
            action="update_relationship",
            params={"affinity_delta": 10, "note": "Friendly chat."},
            latency_ms=1.0,
            used_fallback=False,
            attempts=1,
        )
        fake_decide = _router_decide(
            {
                a_name: ("speak", {"target_agent_id": b_id, "message": "Hello!"}),
                b_name: ("idle", {"reason": "content"}),
            },
            relationship_decision=rel_decision,
        )
        monkeypatch.setattr(engine_module, "decide_action", fake_decide)
        monkeypatch.setattr(engine_module, "generate_text", _fake_reply("Hey, good to see you!"))

        broadcasts = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            broadcasts.append((event_type, payload))

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        a_memories = memory_repo.list_all_memories(conn, a_id)
        b_memories = memory_repo.list_all_memories(conn, b_id)
        assert any(m["type"] == "conversation" for m in a_memories)
        assert any(m["type"] == "conversation" for m in b_memories)

        a_detail = agents_repo.get_agent_detail(conn, a_id)
        b_detail = agents_repo.get_agent_detail(conn, b_id)
        assert a_detail["needs"]["social"] == 100.0
        assert b_detail["needs"]["social"] == 100.0
        assert a_detail["current_goal"] == f"Talked with {b_name}."
        assert b_detail["current_goal"] == f"Talked with {a_name}."

        rel = relationships_repo.get_relationship(conn, a_id, b_id)
        assert rel["affinity"] == 10.0
        assert rel["note"] == "Friendly chat."

        types = [t for t, _ in broadcasts]
        assert "conversation" in types
        assert "relationship_update" in types
    finally:
        conn.close()


async def test_speak_target_out_of_range_falls_back_to_idle(isolated_saves_dir, monkeypatch):
    save_repo.create_save("convrange", population_target=2, world_width=20, world_height=20)
    conn = save_repo.load_save("convrange")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        a_id, b_id = agents[0]["id"], agents[1]["id"]
        a_name, b_name = agents[0]["name"], agents[1]["name"]
        conn.execute("UPDATE agents SET x = 0, y = 0 WHERE id = ?", (a_id,))
        conn.execute("UPDATE agents SET x = 15, y = 15 WHERE id = ?", (b_id,))
        conn.commit()

        fake_decide = _router_decide(
            {
                a_name: ("speak", {"target_agent_id": b_id, "message": "Hello!"}),
                b_name: ("idle", {"reason": "content"}),
            }
        )
        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        a_detail = agents_repo.get_agent_detail(conn, a_id)
        assert a_detail["current_goal"] == "Starting a conversation."

        rejection_logs = [log for log in logs if log.get("rejected")]
        assert rejection_logs
        assert rejection_logs[-1]["rejection_reason"] == "target_unavailable"

        b_detail = agents_repo.get_agent_detail(conn, b_id)
        assert b_detail["current_goal"] == "content"
    finally:
        conn.close()


async def test_speak_to_agent_not_due_this_tick_falls_back_to_idle(isolated_saves_dir, monkeypatch):
    save_repo.create_save("convbusy", population_target=2, world_width=10, world_height=10)
    conn = save_repo.load_save("convbusy")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        a_id, b_id = agents[0]["id"], agents[1]["id"]
        a_name = agents[0]["name"]
        conn.execute("UPDATE agents SET x = 0, y = 0 WHERE id = ?", (a_id,))
        conn.execute(
            "UPDATE agents SET x = 1, y = 0, next_decision_tick = 100 WHERE id = ?", (b_id,)
        )
        conn.commit()

        fake_decide = _router_decide({a_name: ("speak", {"target_agent_id": b_id, "message": "Hi!"})})
        monkeypatch.setattr(engine_module, "decide_action", fake_decide)

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        rejection_logs = [log for log in logs if log.get("rejected")]
        assert rejection_logs
        assert rejection_logs[-1]["rejection_reason"] == "target_unavailable"

        b_memories = memory_repo.list_all_memories(conn, b_id)
        assert not any(m["type"] == "conversation" for m in b_memories)
    finally:
        conn.close()


async def test_mutual_speak_resolves_only_once(isolated_saves_dir, monkeypatch):
    save_repo.create_save("convmutual", population_target=2, world_width=10, world_height=10)
    conn = save_repo.load_save("convmutual")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        a_id, b_id = agents[0]["id"], agents[1]["id"]
        a_name, b_name = agents[0]["name"], agents[1]["name"]
        conn.execute("UPDATE agents SET x = 0, y = 0 WHERE id = ?", (a_id,))
        conn.execute("UPDATE agents SET x = 1, y = 0 WHERE id = ?", (b_id,))
        conn.commit()

        fake_decide = _router_decide(
            {
                a_name: ("speak", {"target_agent_id": b_id, "message": "Hi B!"}),
                b_name: ("speak", {"target_agent_id": a_id, "message": "Hi A!"}),
            },
            relationship_decision=LLMDecision(
                action="update_relationship",
                params={"affinity_delta": 5, "note": "Nice chat."},
                latency_ms=1.0,
                used_fallback=False,
                attempts=1,
            ),
        )
        monkeypatch.setattr(engine_module, "decide_action", fake_decide)
        monkeypatch.setattr(engine_module, "generate_text", _fake_reply("Sure!"))

        conversations = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "conversation":
                conversations.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert len(conversations) == 1
    finally:
        conn.close()
