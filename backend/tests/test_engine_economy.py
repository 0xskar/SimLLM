from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, economy_repo, save_repo
from simllm.sim import engine as engine_module
from simllm.sim.engine import SimulationEngine


def _fake_decide(action: str, params: dict | None = None):
    async def fake(messages, settings, client=None, tools=None):
        return LLMDecision(action=action, params=params or {}, latency_ms=1.0, used_fallback=False, attempts=1)

    return fake


def _setup(isolated_saves_dir, name, population_target=1):
    save_repo.create_save(name, population_target=population_target, world_width=12, world_height=12)
    conn = save_repo.load_save(name)
    settings = save_repo.load_settings(conn)
    agent_id = agents_repo.list_agent_summaries(conn)[0]["id"]
    workplace = conn.execute("SELECT id, x, y FROM buildings WHERE type = 'workplace' LIMIT 1").fetchone()
    job_id = conn.execute("SELECT id FROM jobs WHERE workplace_building_id = ?", (workplace["id"],)).fetchone()["id"]
    return conn, settings, agent_id, workplace, job_id


async def test_take_job_at_workplace_succeeds(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "jobtake")
    try:
        conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (workplace["x"], workplace["y"], agent_id))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("take_job", {"job_id": job_id}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        assignment = economy_repo.get_active_assignment(conn, agent_id)
        assert assignment is not None
        assert assignment["job_id"] == job_id

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["currency"] == settings.starting_currency  # taking a job has no immediate cost/payout
    finally:
        conn.close()


async def test_take_job_rejected_when_not_at_workplace(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "jobfar")
    try:
        # Far corner of the grid -- guaranteed outside workplace_interaction_range
        # regardless of exactly where world_gen happened to place the workplace.
        far_x, far_y = 11, 11
        assert max(abs(workplace["x"] - far_x), abs(workplace["y"] - far_y)) > settings.workplace_interaction_range
        conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (far_x, far_y, agent_id))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("take_job", {"job_id": job_id}))

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert economy_repo.get_active_assignment(conn, agent_id) is None
        assert any(log.get("rejection_reason") == "not_at_workplace" for log in logs)
    finally:
        conn.close()


async def test_take_job_rejected_when_already_employed(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "jobdouble")
    try:
        conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (workplace["x"], workplace["y"], agent_id))
        economy_repo.assign_job(conn, job_id, agent_id, tick=0)
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("take_job", {"job_id": job_id}))

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "already_employed" for log in logs)
    finally:
        conn.close()


async def test_take_job_rejected_when_job_is_full(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "jobfull", population_target=2)
    try:
        # Fill every slot with other (non-decision-relevant) agents.
        job = economy_repo.get_job(conn, job_id)
        for i in range(job["slots"]):
            filler_id = agents_repo.create_agent(
                conn, name=f"Filler{i}", emoji="🙂", traits=[], backstory=None,
                x=workplace["x"], y=workplace["y"], home_building_id=None,
                lifespan_ticks=10000, currency=0.0, generation=1, created_at_tick=0,
            )
            economy_repo.assign_job(conn, job_id, filler_id, tick=0)
        conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (workplace["x"], workplace["y"], agent_id))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("take_job", {"job_id": job_id}))

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        a_logs = [log for log in logs if log.get("agent_id") == agent_id]
        assert any(log.get("rejection_reason") == "job_full" for log in a_logs)
    finally:
        conn.close()


async def test_work_job_pays_wage_and_updates_needs(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "jobwork")
    try:
        conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (workplace["x"], workplace["y"], agent_id))
        economy_repo.assign_job(conn, job_id, agent_id, tick=0)
        conn.execute("UPDATE agent_needs SET purpose = 50.0, energy = 80.0 WHERE agent_id = ?", (agent_id,))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("work_job", {}))

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        wage = economy_repo.get_job(conn, job_id)["wage_per_shift"]
        assert detail["currency"] == settings.starting_currency + wage
        assert detail["needs"]["purpose"] > 50.0
        assert detail["needs"]["energy"] < 80.0

        transaction = conn.execute(
            "SELECT * FROM currency_transactions WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        assert transaction["reason"] == "wage"
        assert transaction["amount"] == wage
    finally:
        conn.close()


async def test_work_job_rejected_without_a_job(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "worknojob")
    try:
        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("work_job", {}))

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "no_job" for log in logs)
        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["currency"] == settings.starting_currency
    finally:
        conn.close()


async def test_work_job_rejected_when_not_at_workplace(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, workplace, job_id = _setup(isolated_saves_dir, "worknotthere")
    try:
        economy_repo.assign_job(conn, job_id, agent_id, tick=0)
        far_x, far_y = 11, 11
        assert max(abs(workplace["x"] - far_x), abs(workplace["y"] - far_y)) > settings.workplace_interaction_range
        conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (far_x, far_y, agent_id))
        conn.commit()

        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("work_job", {}))

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "not_at_workplace" for log in logs)
        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["currency"] == settings.starting_currency
    finally:
        conn.close()
