from __future__ import annotations

import json
import sqlite3

# Canonical set of categories a log entry can carry. Not enforced at the DB
# level (payload is free-form JSON) -- this is the reference list the
# frontend's filter dropdown and this module's callers should stick to.
LOG_CATEGORIES = [
    "system",
    "llm_call",
    "conversation",
    "summarization",
    "emoji",
    "death",
    "newcomer",
]


def add_event(
    conn: sqlite3.Connection,
    *,
    tick: int,
    sim_datetime: str,
    category: str,
    agent_id: int | None,
    payload: dict,
) -> None:
    conn.execute(
        "INSERT INTO events_log (tick, sim_datetime, category, agent_id, payload) VALUES (?, ?, ?, ?, ?)",
        (tick, sim_datetime, category, agent_id, json.dumps(payload)),
    )


def list_events(
    conn: sqlite3.Connection,
    *,
    category: str | None = None,
    limit: int = 200,
    before_tick: int | None = None,
) -> list[dict]:
    """Most-recent-first, for the Logs panel's initial backfill and
    reconnect/pagination -- live updates after that come over the WS
    'log' event, not repeated polling of this endpoint."""
    clauses = []
    params: list[object] = []
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if before_tick is not None:
        clauses.append("tick < ?")
        params.append(before_tick)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT tick, sim_datetime, category, agent_id, payload FROM events_log "
        f"{where} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()

    events = []
    for row in rows:
        payload = json.loads(row["payload"])
        events.append(
            {
                "tick": row["tick"],
                "sim_datetime": row["sim_datetime"],
                "category": row["category"],
                "agent_id": row["agent_id"],
                **payload,
            }
        )
    return events
