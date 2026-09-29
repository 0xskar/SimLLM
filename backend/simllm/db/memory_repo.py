from __future__ import annotations

import sqlite3


def add_memory(
    conn: sqlite3.Connection,
    *,
    agent_id: int,
    tick: int,
    sim_datetime: str,
    type: str,
    content: str,
    related_agent_id: int | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO memories (agent_id, tick, sim_datetime, type, content, related_agent_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (agent_id, tick, sim_datetime, type, content, related_agent_id),
    )
    return cur.lastrowid


def get_recent_memories(conn: sqlite3.Connection, agent_id: int, limit: int) -> list[dict]:
    """Most recent `limit` memories, chronological (oldest first) -- for
    verbatim inclusion in the agent's decision prompt."""
    if limit <= 0:
        return []
    rows = conn.execute(
        "SELECT id, agent_id, tick, sim_datetime, type, content, related_agent_id "
        "FROM memories WHERE agent_id = ? ORDER BY tick DESC, id DESC LIMIT ?",
        (agent_id, limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def get_memories_since_tick(conn: sqlite3.Connection, agent_id: int, since_tick: int) -> list[dict]:
    """All memories strictly after `since_tick`, chronological order -- fed
    to the periodic life-summary LLM call to compress into the running
    summary."""
    rows = conn.execute(
        "SELECT id, agent_id, tick, sim_datetime, type, content, related_agent_id "
        "FROM memories WHERE agent_id = ? AND tick > ? ORDER BY tick ASC, id ASC",
        (agent_id, since_tick),
    ).fetchall()
    return [dict(row) for row in rows]


def list_all_memories(conn: sqlite3.Connection, agent_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
    """Paginated full history (most recent first), for the inspector's
    event log -- unlike the prompt buffer, this is never trimmed."""
    rows = conn.execute(
        "SELECT id, agent_id, tick, sim_datetime, type, content, related_agent_id "
        "FROM memories WHERE agent_id = ? ORDER BY tick DESC, id DESC LIMIT ? OFFSET ?",
        (agent_id, limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]
