from __future__ import annotations

from simllm.db import economy_repo, save_repo


def make_conn_with_workplace(isolated_saves_dir, population_target=4):
    save_repo.create_save("ecotest", population_target=population_target, world_width=12, world_height=12)
    conn = save_repo.load_save("ecotest")
    workplace = conn.execute("SELECT id, x, y FROM buildings WHERE type = 'workplace' LIMIT 1").fetchone()
    return conn, workplace


def test_create_job_and_get_job(isolated_saves_dir):
    conn, workplace = make_conn_with_workplace(isolated_saves_dir)
    try:
        job_id = economy_repo.create_job(conn, workplace["id"], "Baker", 30.0, 2)
        conn.commit()

        job = economy_repo.get_job(conn, job_id)
        assert job["title"] == "Baker"
        assert job["wage_per_shift"] == 30.0
        assert job["slots"] == 2
        assert job["filled"] == 0
        assert job["x"] == workplace["x"]
        assert job["y"] == workplace["y"]
    finally:
        conn.close()


def test_list_jobs_with_openings_includes_workplace_position(isolated_saves_dir):
    # seed_world already creates one job per workplace (Milestone 10) --
    # this test just verifies that auto-seeded job is listed correctly.
    conn, workplace = make_conn_with_workplace(isolated_saves_dir)
    try:
        jobs = economy_repo.list_jobs_with_openings(conn)
        assert len(jobs) == 1
        assert jobs[0]["x"] == workplace["x"]
        assert jobs[0]["y"] == workplace["y"]
        assert jobs[0]["filled"] == 0
    finally:
        conn.close()


def test_assign_job_increments_filled_count(isolated_saves_dir):
    conn, workplace = make_conn_with_workplace(isolated_saves_dir)
    try:
        job_id = economy_repo.create_job(conn, workplace["id"], "Worker", 25.0, 2)
        conn.commit()
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]

        economy_repo.assign_job(conn, job_id, agent_id, tick=5)
        conn.commit()

        job = economy_repo.get_job(conn, job_id)
        assert job["filled"] == 1
    finally:
        conn.close()


def test_get_active_assignment_returns_none_when_unemployed(isolated_saves_dir):
    conn, _ = make_conn_with_workplace(isolated_saves_dir)
    try:
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        assert economy_repo.get_active_assignment(conn, agent_id) is None
    finally:
        conn.close()


def test_get_active_assignment_returns_job_details(isolated_saves_dir):
    conn, workplace = make_conn_with_workplace(isolated_saves_dir)
    try:
        job_id = economy_repo.create_job(conn, workplace["id"], "Worker", 25.0, 2)
        conn.commit()
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        economy_repo.assign_job(conn, job_id, agent_id, tick=1)
        conn.commit()

        assignment = economy_repo.get_active_assignment(conn, agent_id)
        assert assignment["job_id"] == job_id
        assert assignment["wage_per_shift"] == 25.0
        assert assignment["x"] == workplace["x"]
    finally:
        conn.close()


def test_record_transaction_persists_row(isolated_saves_dir):
    conn, _ = make_conn_with_workplace(isolated_saves_dir)
    try:
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        economy_repo.record_transaction(conn, agent_id, tick=3, amount=25.0, reason="wage", balance_after=125.0)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM currency_transactions WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        assert row["amount"] == 25.0
        assert row["reason"] == "wage"
        assert row["balance_after"] == 125.0
    finally:
        conn.close()


def test_release_job_assignment_frees_the_slot(isolated_saves_dir):
    conn, workplace = make_conn_with_workplace(isolated_saves_dir)
    try:
        job_id = economy_repo.create_job(conn, workplace["id"], "Worker", 25.0, 2)
        conn.commit()
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        economy_repo.assign_job(conn, job_id, agent_id, tick=0)
        conn.commit()
        assert economy_repo.get_job(conn, job_id)["filled"] == 1

        economy_repo.release_job_assignment(conn, agent_id)
        conn.commit()

        assert economy_repo.get_job(conn, job_id)["filled"] == 0
        assert economy_repo.get_active_assignment(conn, agent_id) is None
    finally:
        conn.close()
