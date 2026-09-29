from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine
from simllm.sim.mood import compute_mood, compute_mood_band


def _router_decide(main_action="idle", main_params=None, emoji_decision=None):
    async def fake(messages, settings, client=None, tools=None):
        if tools is not None:
            if emoji_decision is not None:
                return emoji_decision
            return LLMDecision(
                action="idle", params={}, latency_ms=1.0, used_fallback=True, attempts=1, error="unconfigured"
            )
        return LLMDecision(
            action=main_action, params=main_params or {}, latency_ms=1.0, used_fallback=False, attempts=1
        )

    return fake


async def test_mood_is_computed_and_persisted_every_tick(isolated_saves_dir, monkeypatch):
    save_repo.create_save("moodtick", population_target=1)
    conn = save_repo.load_save("moodtick")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        monkeypatch.setattr(engine_module, "decide_action", _router_decide("idle", {"reason": "content"}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        expected_mood = compute_mood(detail["needs"], detail["health"])
        assert abs(detail["mood"] - expected_mood) < 0.01
        assert detail["mood_band"] == compute_mood_band(expected_mood, settings.mood_band_width)
    finally:
        conn.close()


async def test_emoji_repicked_when_mood_band_changes(isolated_saves_dir, monkeypatch):
    # A fresh agent starts at mood_band=0 but immediately computes a high
    # positive mood (needs/health start maxed) -- this alone crosses bands
    # and should trigger a repick on the very first tick.
    save_repo.create_save("moodrepick", population_target=1)
    conn = save_repo.load_save("moodrepick")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        emoji_decision = LLMDecision(
            action="pick_emoji", params={"emoji": "🥳"}, latency_ms=1.0, used_fallback=False, attempts=1
        )
        monkeypatch.setattr(
            engine_module, "decide_action",
            _router_decide("idle", {"reason": "content"}, emoji_decision=emoji_decision),
        )

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["emoji"] == "🥳"
    finally:
        conn.close()


async def test_emoji_not_repicked_when_band_unchanged(isolated_saves_dir, monkeypatch):
    save_repo.create_save("moodstable", population_target=1)
    conn = save_repo.load_save("moodstable")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        emoji_calls = {"count": 0}

        async def fake(messages, settings_arg, client=None, tools=None):
            if tools is not None:
                emoji_calls["count"] += 1
                return LLMDecision(
                    action="pick_emoji", params={"emoji": "🥳"}, latency_ms=1.0, used_fallback=False, attempts=1
                )
            return LLMDecision(action="idle", params={"reason": "content"}, latency_ms=1.0, used_fallback=False, attempts=1)

        monkeypatch.setattr(engine_module, "decide_action", fake)

        engine = SimulationEngine(conn, settings, None)
        # First tick: mood_band moves from the default (0) to "great" -- a
        # real crossing, so a repick fires exactly once.
        await engine.run_tick()
        assert emoji_calls["count"] == 1
        assert agents_repo.get_agent_detail(conn, agent_id)["emoji"] == "🥳"

        # Second tick: mood barely moves from one more tick of decay, same
        # band -- no further repick, emoji stays whatever it was just set to.
        await engine.run_tick()
        assert emoji_calls["count"] == 1
        assert agents_repo.get_agent_detail(conn, agent_id)["emoji"] == "🥳"
    finally:
        conn.close()


async def test_emoji_repick_failure_keeps_old_emoji(isolated_saves_dir, monkeypatch):
    save_repo.create_save("moodfail", population_target=1)
    conn = save_repo.load_save("moodfail")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        original_emoji = agents_repo.get_agent_detail(conn, agent_id)["emoji"]

        failing_emoji_decision = LLMDecision(
            action="idle", params={}, latency_ms=0.0, used_fallback=True, attempts=2, error="timeout"
        )
        monkeypatch.setattr(
            engine_module, "decide_action",
            _router_decide("idle", {"reason": "content"}, emoji_decision=failing_emoji_decision),
        )

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        assert agents_repo.get_agent_detail(conn, agent_id)["emoji"] == original_emoji
    finally:
        conn.close()


async def test_agent_stat_update_broadcast_includes_mood(isolated_saves_dir, monkeypatch):
    save_repo.create_save("moodbroadcast", population_target=1)
    conn = save_repo.load_save("moodbroadcast")
    try:
        settings = save_repo.load_settings(conn)
        monkeypatch.setattr(engine_module, "decide_action", _router_decide("idle", {"reason": "content"}))

        stat_updates = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "agent_stat_update" and "needs" in payload:
                stat_updates.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert stat_updates
        assert "mood" in stat_updates[0]
    finally:
        conn.close()


async def test_non_emoji_text_reply_is_rejected_and_keeps_old_emoji(isolated_saves_dir, monkeypatch):
    # Small models sometimes return a text emoticon (e.g. ":)") instead of a
    # real emoji glyph -- that should never overwrite a good emoji with
    # unrenderable garbage.
    save_repo.create_save("moodtextemoji", population_target=1)
    conn = save_repo.load_save("moodtextemoji")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        original_emoji = agents_repo.get_agent_detail(conn, agent_id)["emoji"]

        bad_emoji_decision = LLMDecision(
            action="pick_emoji", params={"emoji": ":)"}, latency_ms=1.0, used_fallback=False, attempts=1
        )
        monkeypatch.setattr(
            engine_module, "decide_action",
            _router_decide("idle", {"reason": "content"}, emoji_decision=bad_emoji_decision),
        )

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        assert agents_repo.get_agent_detail(conn, agent_id)["emoji"] == original_emoji
    finally:
        conn.close()
