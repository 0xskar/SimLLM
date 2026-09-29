from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, economy_repo, save_repo, world_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


def _fake_decide(action: str, params: dict | None = None):
    async def fake(messages, settings, client=None, tools=None):
        return LLMDecision(action=action, params=params or {}, latency_ms=1.0, used_fallback=False, attempts=1)

    return fake


def _fake_personality(name="Newcomer", emoji="🎉", backstory="A fresh start.", traits=None):
    async def fake(messages, settings, client=None, tools=None):
        return LLMDecision(
            action="create_personality",
            params={"name": name, "backstory": backstory, "traits": traits or ["curious"], "emoji": emoji},
            latency_ms=1.0,
            used_fallback=False,
            attempts=1,
        )

    return fake


async def test_age_death_marks_agent_dead_and_broadcasts(isolated_saves_dir, monkeypatch):
    save_repo.create_save("agedeath", population_target=1)
    conn = save_repo.load_save("agedeath")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        conn.execute("UPDATE agents SET lifespan_ticks = 1 WHERE id = ?", (agent_id,))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "content"}))

        events = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            events.append((event_type, payload))

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["is_alive"] == 0
        assert detail["death_cause"] == "age"
        assert detail["death_tick"] == 1

        death_events = [p for (t, p) in events if t == "agent_death"]
        assert death_events == [{"agent_id": agent_id, "cause": "age"}]
    finally:
        conn.close()


async def test_starvation_death_after_sustained_zero_health(isolated_saves_dir, monkeypatch):
    save_repo.create_save("starvedeath", population_target=1)
    conn = save_repo.load_save("starvedeath")
    try:
        settings = save_repo.load_settings(conn)
        settings.starvation_death_ticks = 3
        save_repo.save_settings(conn, settings)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        conn.execute("UPDATE agents SET health = 0, lifespan_ticks = 999999 WHERE id = ?", (agent_id,))
        # All needs critical so health never regenerates.
        conn.execute(
            "UPDATE agent_needs SET hunger=0, energy=0, social=0, shelter=0, hygiene=0, fun=0, purpose=0 "
            "WHERE agent_id = ?",
            (agent_id,),
        )
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "starving"}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()  # streak 1
        assert agents_repo.get_agent_detail(conn, agent_id)["is_alive"] == 1
        await engine.run_tick()  # streak 2
        assert agents_repo.get_agent_detail(conn, agent_id)["is_alive"] == 1
        await engine.run_tick()  # streak 3 -> death

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["is_alive"] == 0
        assert detail["death_cause"] == "starvation"
    finally:
        conn.close()


async def test_health_recovery_resets_zero_health_streak(isolated_saves_dir, monkeypatch):
    save_repo.create_save("recoverdeath", population_target=1)
    conn = save_repo.load_save("recoverdeath")
    try:
        settings = save_repo.load_settings(conn)
        settings.starvation_death_ticks = 3
        save_repo.save_settings(conn, settings)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        conn.execute(
            "UPDATE agents SET health = 0, lifespan_ticks = 999999, zero_health_ticks = 2 WHERE id = ?",
            (agent_id,),
        )
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "content"}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()  # needs are healthy -> health regenerates above 0, streak resets

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["is_alive"] == 1
        assert detail["zero_health_ticks"] == 0
    finally:
        conn.close()


async def test_death_releases_job_and_home(isolated_saves_dir, monkeypatch):
    # Any single death always drops population below whatever it started
    # at (since it started exactly at target), which would otherwise trigger
    # a same-tick respawn that immediately reclaims the just-vacated house.
    # Lower the target after seeding so this tick's death doesn't trigger one,
    # isolating the release behavior this test actually cares about.
    save_repo.create_save("deathrelease", population_target=2, world_width=12, world_height=12)
    conn = save_repo.load_save("deathrelease")
    try:
        settings = save_repo.load_settings(conn)
        settings.population_target = 1
        save_repo.save_settings(conn, settings)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        home = conn.execute("SELECT home_building_id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        home_building_id = home["home_building_id"]
        workplace = conn.execute("SELECT id FROM buildings WHERE type = 'workplace' LIMIT 1").fetchone()
        job_id = conn.execute("SELECT id FROM jobs WHERE workplace_building_id = ?", (workplace["id"],)).fetchone()["id"]
        economy_repo.assign_job(conn, job_id, agent_id, tick=0)
        conn.execute("UPDATE agents SET lifespan_ticks = 1 WHERE id = ?", (agent_id,))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "content"}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        assert world_repo.get_building(conn, home_building_id)["owner_agent_id"] is None
        assert economy_repo.get_job(conn, job_id)["filled"] == 0
        assert economy_repo.get_active_assignment(conn, agent_id) is None
    finally:
        conn.close()


async def test_final_wage_payment_persists_even_if_agent_dies_same_tick(isolated_saves_dir, monkeypatch):
    save_repo.create_save("deathwage", population_target=1, world_width=12, world_height=12)
    conn = save_repo.load_save("deathwage")
    try:
        settings = save_repo.load_settings(conn)
        agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
        workplace = conn.execute("SELECT id, x, y FROM buildings WHERE type = 'workplace' LIMIT 1").fetchone()
        job_id = conn.execute(
            "SELECT id FROM jobs WHERE workplace_building_id = ?", (workplace["id"],)
        ).fetchone()["id"]
        economy_repo.assign_job(conn, job_id, agent_id, tick=0)
        conn.execute(
            "UPDATE agents SET x = ?, y = ?, lifespan_ticks = 1, currency = 50.0 WHERE id = ?",
            (workplace["x"], workplace["y"], agent_id),
        )
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("work_job", {}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        wage = economy_repo.get_job(conn, job_id)["wage_per_shift"]
        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["is_alive"] == 0
        assert detail["currency"] == 50.0 + wage  # wage wasn't lost despite dying this same tick
    finally:
        conn.close()


async def test_respawn_creates_newcomer_when_below_population_target(isolated_saves_dir, monkeypatch):
    save_repo.create_save("respawn1", population_target=2)
    conn = save_repo.load_save("respawn1")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        agents_repo.mark_agent_dead(conn, agents[0]["id"], tick=0, cause="age")
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_personality())

        created = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "agent_created":
                created.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        population = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1").fetchone()["c"]
        assert population == 2
        assert len(created) == 1
        assert created[0]["name"] == "Newcomer"
        assert created[0]["emoji"] == "🎉"
    finally:
        conn.close()


async def test_respawn_reuses_a_vacant_house(isolated_saves_dir, monkeypatch):
    save_repo.create_save("respawn2", population_target=2)
    conn = save_repo.load_save("respawn2")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        dead_agent = agents_repo.get_agent_detail(conn, agents[0]["id"])
        vacated_house_id = dead_agent["home_building_id"]
        agents_repo.mark_agent_dead(conn, agents[0]["id"], tick=0, cause="age")
        world_repo.release_building_owner(conn, vacated_house_id)
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_personality())

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        newcomer = conn.execute(
            "SELECT id, home_building_id FROM agents WHERE is_alive = 1 AND name = 'Newcomer'"
        ).fetchone()
        assert newcomer["home_building_id"] == vacated_house_id
        assert world_repo.get_building(conn, vacated_house_id)["owner_agent_id"] == newcomer["id"]
    finally:
        conn.close()


async def test_respawn_falls_back_to_placeholder_identity_when_llm_fails(isolated_saves_dir, monkeypatch):
    save_repo.create_save("respawn3", population_target=2)
    conn = save_repo.load_save("respawn3")
    try:
        settings = save_repo.load_settings(conn)
        agents = agents_repo.list_agent_summaries(conn)
        agents_repo.mark_agent_dead(conn, agents[0]["id"], tick=0, cause="age")
        conn.commit()

        async def failing_decide(messages, settings_arg, client=None, tools=None):
            return LLMDecision(
                action="idle", params={}, latency_ms=0.0, used_fallback=True, attempts=2, error="timeout"
            )

        monkeypatch.setattr(engine_module, "decide_action", failing_decide)

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        population = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1").fetchone()["c"]
        assert population == 2  # respawn still happened despite the LLM failure
    finally:
        conn.close()


async def test_respawn_increments_generation(isolated_saves_dir, monkeypatch):
    save_repo.create_save("respawn4", population_target=2)
    conn = save_repo.load_save("respawn4")
    try:
        settings = save_repo.load_settings(conn)
        before_gen = conn.execute("SELECT generation FROM sim_clock WHERE id = 1").fetchone()["generation"]
        agents = agents_repo.list_agent_summaries(conn)
        agents_repo.mark_agent_dead(conn, agents[0]["id"], tick=0, cause="age")
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_personality())

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        after_gen = conn.execute("SELECT generation FROM sim_clock WHERE id = 1").fetchone()["generation"]
        assert after_gen == before_gen + 1
    finally:
        conn.close()


async def test_no_respawn_when_population_at_target(isolated_saves_dir, monkeypatch):
    save_repo.create_save("respawn5", population_target=1)
    conn = save_repo.load_save("respawn5")
    try:
        settings = save_repo.load_settings(conn)
        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "content"}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        population = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1").fetchone()["c"]
        assert population == 1
    finally:
        conn.close()
