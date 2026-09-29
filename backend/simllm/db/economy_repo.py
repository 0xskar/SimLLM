from __future__ import annotations

import sqlite3


def create_job(
    conn: sqlite3.Connection, workplace_building_id: int, title: str, wage_per_shift: float, slots: int
) -> int:
    cur = conn.execute(
        "INSERT INTO jobs (workplace_building_id, title, wage_per_shift, slots) VALUES (?, ?, ?, ?)",
        (workplace_building_id, title, wage_per_shift, slots),
    )
    return cur.lastrowid


def list_jobs_with_openings(conn: sqlite3.Connection) -> list[dict]:
    """Every job with its workplace position and current filled-slot count,
    fetched once per tick and shared across all due agents' perception
    filtering (same pattern as tiles/buildings/agent snapshots)."""
    rows = conn.execute(
        """
        SELECT j.id, j.workplace_building_id, j.title, j.wage_per_shift, j.slots, b.x, b.y,
               (SELECT COUNT(*) FROM job_assignments ja WHERE ja.job_id = j.id AND ja.active = 1) AS filled
        FROM jobs j
        JOIN buildings b ON b.id = j.workplace_building_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_job(conn: sqlite3.Connection, job_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT j.id, j.workplace_building_id, j.title, j.wage_per_shift, j.slots, b.x, b.y,
               (SELECT COUNT(*) FROM job_assignments ja WHERE ja.job_id = j.id AND ja.active = 1) AS filled
        FROM jobs j
        JOIN buildings b ON b.id = j.workplace_building_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


def get_active_assignment(conn: sqlite3.Connection, agent_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT ja.id AS assignment_id, ja.job_id, ja.agent_id, ja.started_tick,
               j.title, j.wage_per_shift, j.workplace_building_id, b.x, b.y
        FROM job_assignments ja
        JOIN jobs j ON j.id = ja.job_id
        JOIN buildings b ON b.id = j.workplace_building_id
        WHERE ja.agent_id = ? AND ja.active = 1
        """,
        (agent_id,),
    ).fetchone()
    return dict(row) if row else None


def assign_job(conn: sqlite3.Connection, job_id: int, agent_id: int, tick: int) -> int:
    cur = conn.execute(
        "INSERT INTO job_assignments (job_id, agent_id, started_tick, active) VALUES (?, ?, ?, 1)",
        (job_id, agent_id, tick),
    )
    return cur.lastrowid


def release_job_assignment(conn: sqlite3.Connection, agent_id: int) -> None:
    """Frees this agent's active job slot (e.g. on death) so someone else
    can take it."""
    conn.execute("UPDATE job_assignments SET active = 0 WHERE agent_id = ? AND active = 1", (agent_id,))


def record_transaction(
    conn: sqlite3.Connection, agent_id: int, tick: int, amount: float, reason: str, balance_after: float
) -> None:
    conn.execute(
        "INSERT INTO currency_transactions (agent_id, tick, amount, reason, balance_after) VALUES (?, ?, ?, ?, ?)",
        (agent_id, tick, amount, reason, balance_after),
    )
