from __future__ import annotations

import sqlite3


def _normalize_pair(agent_a_id: int, agent_b_id: int) -> tuple[int, int]:
    return (agent_a_id, agent_b_id) if agent_a_id < agent_b_id else (agent_b_id, agent_a_id)


def clamp_affinity(value: float) -> float:
    return max(-100.0, min(100.0, value))


def get_relationship(conn: sqlite3.Connection, agent_a_id: int, agent_b_id: int) -> dict | None:
    a, b = _normalize_pair(agent_a_id, agent_b_id)
    row = conn.execute(
        "SELECT agent_a_id, agent_b_id, affinity, note, updated_tick FROM relationships "
        "WHERE agent_a_id = ? AND agent_b_id = ?",
        (a, b),
    ).fetchone()
    return dict(row) if row else None


def upsert_relationship(
    conn: sqlite3.Connection, agent_a_id: int, agent_b_id: int, affinity: float, note: str, tick: int
) -> None:
    a, b = _normalize_pair(agent_a_id, agent_b_id)
    conn.execute(
        "INSERT INTO relationships (agent_a_id, agent_b_id, affinity, note, updated_tick) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(agent_a_id, agent_b_id) DO UPDATE SET "
        "affinity = excluded.affinity, note = excluded.note, updated_tick = excluded.updated_tick",
        (a, b, affinity, note, tick),
    )


def list_relationships_for_agent(conn: sqlite3.Connection, agent_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT r.affinity, r.note, r.updated_tick,
               a.id AS other_id, a.name AS other_name, a.emoji AS other_emoji
        FROM relationships r
        JOIN agents a ON a.id = CASE WHEN r.agent_a_id = ? THEN r.agent_b_id ELSE r.agent_a_id END
        WHERE r.agent_a_id = ? OR r.agent_b_id = ?
        ORDER BY r.updated_tick DESC
        """,
        (agent_id, agent_id, agent_id),
    ).fetchall()
    return [
        {
            "other_agent_id": row["other_id"],
            "other_name": row["other_name"],
            "other_emoji": row["other_emoji"],
            "affinity": row["affinity"],
            "note": row["note"],
            "updated_tick": row["updated_tick"],
        }
        for row in rows
    ]
