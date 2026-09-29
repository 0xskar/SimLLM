from __future__ import annotations

from simllm.db import agents_repo, save_repo


def test_mark_agent_dead_sets_fields(isolated_saves_dir):
    save_repo.create_save("deadtest", population_target=1)
    conn = save_repo.load_save("deadtest")
    try:
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        agents_repo.mark_agent_dead(conn, agent_id, tick=42, cause="starvation")
        conn.commit()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["is_alive"] == 0
        assert detail["death_tick"] == 42
        assert detail["death_cause"] == "starvation"
    finally:
        conn.close()


def test_dead_agent_excluded_from_summaries_and_tick_states(isolated_saves_dir):
    save_repo.create_save("deadtest2", population_target=2)
    conn = save_repo.load_save("deadtest2")
    try:
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        agents_repo.mark_agent_dead(conn, agent_id, tick=1, cause="age")
        conn.commit()

        tick_states = agents_repo.list_agent_tick_states(conn)
        assert agent_id not in [s["id"] for s in tick_states]

        population = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1").fetchone()["c"]
        assert population == 1
    finally:
        conn.close()


def test_list_agent_tick_states_includes_lifespan_and_zero_health_fields(isolated_saves_dir):
    save_repo.create_save("deadtest3", population_target=1)
    conn = save_repo.load_save("deadtest3")
    try:
        states = agents_repo.list_agent_tick_states(conn)
        assert len(states) == 1
        state = states[0]
        assert "age_ticks" in state
        assert "lifespan_ticks" in state
        assert "zero_health_ticks" in state
        assert "home_building_id" in state
        assert "name" in state
        assert "mood_band" in state
        assert state["zero_health_ticks"] == 0
        assert state["mood_band"] == 0
    finally:
        conn.close()


def test_update_emoji_persists(isolated_saves_dir):
    save_repo.create_save("emojitest", population_target=1)
    conn = save_repo.load_save("emojitest")
    try:
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]

        agents_repo.update_emoji(conn, agent_id, "🥳")
        conn.commit()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["emoji"] == "🥳"
    finally:
        conn.close()
