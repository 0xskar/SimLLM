from __future__ import annotations

import json
import sqlite3

from simllm.sim.needs import NEED_FIELDS


def create_agent(
    conn: sqlite3.Connection,
    *,
    name: str,
    emoji: str,
    traits: list[dict],
    backstory: str | None,
    x: int,
    y: int,
    home_building_id: int | None,
    lifespan_ticks: int,
    currency: float,
    generation: int,
    created_at_tick: int,
) -> int:
    cur = conn.execute(
        "INSERT INTO agents "
        "(name, emoji, traits, backstory, lifespan_ticks, x, y, "
        "home_building_id, currency, generation, created_at_tick) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            emoji,
            json.dumps(traits),
            backstory,
            lifespan_ticks,
            x,
            y,
            home_building_id,
            currency,
            generation,
            created_at_tick,
        ),
    )
    agent_id = cur.lastrowid
    conn.execute(
        "INSERT INTO agent_needs (agent_id, updated_tick) VALUES (?, ?)",
        (agent_id, created_at_tick),
    )
    conn.commit()
    return agent_id


def list_all_agent_snapshots(conn: sqlite3.Connection) -> list[dict]:
    """Lightweight snapshot of every alive agent, fetched once per tick and
    shared across all due agents' perception filtering (see sim/perception.py)
    -- cheaper than a separate radius query per agent, and positions don't
    change again until the next tick's batch pass."""
    rows = conn.execute(
        "SELECT id, name, emoji, x, y, current_goal FROM agents WHERE is_alive = 1"
    ).fetchall()
    return [dict(row) for row in rows]


def list_agent_summaries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, emoji, x, y, is_alive FROM agents ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def get_agent_detail(conn: sqlite3.Connection, agent_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT a.*, n.hunger, n.energy, n.social, n.shelter, n.hygiene, n.fun, n.purpose
        FROM agents a
        JOIN agent_needs n ON n.agent_id = a.id
        WHERE a.id = ?
        """,
        (agent_id,),
    ).fetchone()
    if row is None:
        return None

    detail = dict(row)
    detail["traits"] = json.loads(detail["traits"]) if detail["traits"] else []
    detail["needs"] = {key: detail.pop(key) for key in NEED_FIELDS}
    return detail


def list_agents_for_summary_check(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, life_summary, life_summary_updated_tick, created_at_tick "
        "FROM agents WHERE is_alive = 1"
    ).fetchall()
    return [dict(row) for row in rows]


def update_life_summary(conn: sqlite3.Connection, agent_id: int, summary: str, tick: int) -> None:
    conn.execute(
        "UPDATE agents SET life_summary = ?, life_summary_updated_tick = ? WHERE id = ?",
        (summary, tick, agent_id),
    )


def set_home_building(conn: sqlite3.Connection, agent_id: int, building_id: int) -> None:
    conn.execute("UPDATE agents SET home_building_id = ? WHERE id = ?", (building_id, agent_id))


def list_agent_tick_states(conn: sqlite3.Connection) -> list[dict]:
    """Fetch everything a tick pass needs for every alive agent."""
    rows = conn.execute(
        """
        SELECT a.id, a.name, a.x, a.y, a.home_building_id, a.currency, a.health,
               a.current_action, a.current_goal, a.next_decision_tick,
               a.age_ticks, a.lifespan_ticks, a.zero_health_ticks, a.mood_band,
               b.x AS home_x, b.y AS home_y,
               n.hunger, n.energy, n.social, n.shelter, n.hygiene, n.fun, n.purpose
        FROM agents a
        JOIN agent_needs n ON n.agent_id = a.id
        LEFT JOIN buildings b ON b.id = a.home_building_id
        WHERE a.is_alive = 1
        ORDER BY a.id
        """
    ).fetchall()

    states = []
    for row in rows:
        home_pos = None
        if row["home_building_id"] is not None:
            home_pos = (row["home_x"], row["home_y"])
        states.append(
            {
                "id": row["id"],
                "name": row["name"],
                "x": row["x"],
                "y": row["y"],
                "home_pos": home_pos,
                "home_building_id": row["home_building_id"],
                "currency": row["currency"],
                "health": row["health"],
                "current_action": json.loads(row["current_action"]) if row["current_action"] else None,
                "current_goal": row["current_goal"],
                "next_decision_tick": row["next_decision_tick"],
                "age_ticks": row["age_ticks"],
                "lifespan_ticks": row["lifespan_ticks"],
                "zero_health_ticks": row["zero_health_ticks"],
                "mood_band": row["mood_band"],
                "needs": {key: row[key] for key in NEED_FIELDS},
            }
        )
    return states


def apply_tick_update(
    conn: sqlite3.Connection,
    agent_id: int,
    *,
    x: int,
    y: int,
    needs: dict,
    health: float,
    currency: float,
    current_action: dict | None,
    current_goal: str | None,
    next_decision_tick: int,
    zero_health_ticks: int,
    mood: float,
    mood_band: int,
    tick: int,
) -> None:
    """Persist everything about an agent that can change in a single tick.

    Called once per alive agent per tick -- for a due agent, with the full
    effect of its decision; for a non-due agent, with just its decay and
    (if mid-move) one step of movement, everything else passed through
    unchanged. Not called at all if the agent died this tick -- see
    mark_agent_dead.
    """
    conn.execute(
        "UPDATE agents SET x = ?, y = ?, health = ?, currency = ?, current_action = ?, "
        "current_goal = ?, age_ticks = age_ticks + 1, next_decision_tick = ?, "
        "zero_health_ticks = ?, mood = ?, mood_band = ? WHERE id = ?",
        (
            x, y, health, currency,
            json.dumps(current_action) if current_action else None,
            current_goal, next_decision_tick, zero_health_ticks, mood, mood_band, agent_id,
        ),
    )
    conn.execute(
        "UPDATE agent_needs SET hunger = ?, energy = ?, social = ?, shelter = ?, "
        "hygiene = ?, fun = ?, purpose = ?, updated_tick = ? WHERE agent_id = ?",
        (
            needs["hunger"],
            needs["energy"],
            needs["social"],
            needs["shelter"],
            needs["hygiene"],
            needs["fun"],
            needs["purpose"],
            tick,
            agent_id,
        ),
    )


def update_emoji(conn: sqlite3.Connection, agent_id: int, emoji: str) -> None:
    conn.execute("UPDATE agents SET emoji = ? WHERE id = ?", (emoji, agent_id))


def mark_agent_dead(conn: sqlite3.Connection, agent_id: int, tick: int, cause: str) -> None:
    conn.execute(
        "UPDATE agents SET is_alive = 0, death_tick = ?, death_cause = ? WHERE id = ?",
        (tick, cause, agent_id),
    )
