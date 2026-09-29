from __future__ import annotations

from simllm.agents.llm_client import LLMDecision
from simllm.db import agents_repo, economy_repo, save_repo, world_repo
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
    # Default starting_currency (100) is less than building_costs.house (150)
    # by design -- an agent has to earn wages before they can build. Top up
    # so tests that expect a successful build aren't accidentally exercising
    # the insufficient_funds path instead.
    conn.execute("UPDATE agents SET currency = 1000.0 WHERE id = ?", (agent_id,))
    conn.commit()
    empty = conn.execute("SELECT x, y FROM world_tiles WHERE tile_type = 'empty' LIMIT 1").fetchone()
    return conn, settings, agent_id, (empty["x"], empty["y"])


async def _place_agent_adjacent_to(conn, agent_id, x, y):
    conn.execute("UPDATE agents SET x = ?, y = ? WHERE id = ?", (x, y, agent_id))
    conn.commit()


async def test_start_build_succeeds_deducts_currency_and_creates_site(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, (ex, ey) = _setup(isolated_saves_dir, "buildok")
    try:
        await _place_agent_adjacent_to(conn, agent_id, ex, ey)
        monkeypatch.setattr(
            engine_module, "decide_action",
            _fake_decide("start_build", {"building_type": "house", "target_x": ex, "target_y": ey}),
        )

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()

        detail = agents_repo.get_agent_detail(conn, agent_id)
        assert detail["currency"] == 1000.0 - settings.building_costs.house

        assert world_repo.get_tile_type(conn, ex, ey) == "under_construction"
        transaction = conn.execute(
            "SELECT * FROM currency_transactions WHERE agent_id = ? AND reason = 'building_cost'", (agent_id,)
        ).fetchone()
        assert transaction["amount"] == -settings.building_costs.house
    finally:
        conn.close()


async def test_start_build_rejected_when_not_adjacent(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, (ex, ey) = _setup(isolated_saves_dir, "buildfar")
    try:
        far_x, far_y = 11, 11
        assert max(abs(ex - far_x), abs(ey - far_y)) > 1
        await _place_agent_adjacent_to(conn, agent_id, far_x, far_y)
        monkeypatch.setattr(
            engine_module, "decide_action",
            _fake_decide("start_build", {"building_type": "house", "target_x": ex, "target_y": ey}),
        )

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "invalid_build_site" for log in logs)
        assert world_repo.get_tile_type(conn, ex, ey) == "empty"
    finally:
        conn.close()


async def test_start_build_rejected_when_tile_not_empty(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, _ = _setup(isolated_saves_dir, "buildoccupied")
    try:
        house = conn.execute("SELECT x, y FROM buildings WHERE type = 'house' LIMIT 1").fetchone()
        await _place_agent_adjacent_to(conn, agent_id, house["x"], house["y"])
        monkeypatch.setattr(
            engine_module, "decide_action",
            _fake_decide("start_build", {"building_type": "house", "target_x": house["x"], "target_y": house["y"]}),
        )

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "invalid_build_site" for log in logs)
    finally:
        conn.close()


async def test_start_build_rejected_when_insufficient_funds(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, (ex, ey) = _setup(isolated_saves_dir, "buildpoor")
    try:
        await _place_agent_adjacent_to(conn, agent_id, ex, ey)
        conn.execute("UPDATE agents SET currency = 1.0 WHERE id = ?", (agent_id,))
        conn.commit()
        monkeypatch.setattr(
            engine_module, "decide_action",
            _fake_decide("start_build", {"building_type": "house", "target_x": ex, "target_y": ey}),
        )

        logs = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "log":
                logs.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()

        assert any(log.get("rejection_reason") == "insufficient_funds" for log in logs)
        assert world_repo.get_tile_type(conn, ex, ey) == "empty"
    finally:
        conn.close()


async def test_house_construction_completes_and_becomes_home(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, (ex, ey) = _setup(isolated_saves_dir, "buildcomplete")
    try:
        settings.building_construction_ticks = settings.building_construction_ticks.model_copy(
            update={"house": 2}
        )
        save_repo.save_settings(conn, settings)
        await _place_agent_adjacent_to(conn, agent_id, ex, ey)

        monkeypatch.setattr(
            engine_module, "decide_action",
            _fake_decide("start_build", {"building_type": "house", "target_x": ex, "target_y": ey}),
        )

        building_updates = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            if event_type == "building_update":
                building_updates.append(payload)

        engine = SimulationEngine(conn, settings, fake_broadcast)
        await engine.run_tick()  # start_build issued, 0/2 progress
        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "waiting"}))
        await engine.run_tick()  # progress 1/2
        await engine.run_tick()  # progress 2/2 -> complete

        assert world_repo.get_tile_type(conn, ex, ey) == "house"
        detail = agents_repo.get_agent_detail(conn, agent_id)
        new_house = conn.execute(
            "SELECT id FROM buildings WHERE x = ? AND y = ?", (ex, ey)
        ).fetchone()
        assert detail["home_building_id"] == new_house["id"]

        completions = [u for u in building_updates if u["status"] == "complete"]
        assert len(completions) == 1
    finally:
        conn.close()


async def test_workplace_construction_completes_and_creates_job(isolated_saves_dir, monkeypatch):
    conn, settings, agent_id, (ex, ey) = _setup(isolated_saves_dir, "buildworkplace")
    try:
        settings.building_construction_ticks = settings.building_construction_ticks.model_copy(
            update={"workplace": 1}
        )
        save_repo.save_settings(conn, settings)
        await _place_agent_adjacent_to(conn, agent_id, ex, ey)

        monkeypatch.setattr(
            engine_module, "decide_action",
            _fake_decide("start_build", {"building_type": "workplace", "target_x": ex, "target_y": ey}),
        )

        engine = SimulationEngine(conn, settings, None)
        await engine.run_tick()  # start_build issued
        monkeypatch.setattr(engine_module, "decide_action", _fake_decide("idle", {"reason": "waiting"}))
        await engine.run_tick()  # 1/1 -> complete

        assert world_repo.get_tile_type(conn, ex, ey) == "workplace"
        new_workplace = conn.execute(
            "SELECT id FROM buildings WHERE x = ? AND y = ?", (ex, ey)
        ).fetchone()
        job = conn.execute(
            "SELECT * FROM jobs WHERE workplace_building_id = ?", (new_workplace["id"],)
        ).fetchone()
        assert job is not None
        assert job["wage_per_shift"] == settings.default_job_wage
    finally:
        conn.close()
