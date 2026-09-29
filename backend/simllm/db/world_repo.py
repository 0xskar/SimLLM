from __future__ import annotations

import sqlite3

# Tiles an agent can't walk through. A tile in this set is still walkable if
# it's the agent's own destination -- see pathfinding.find_path.
BLOCKING_TILE_TYPES = ("house", "workplace", "under_construction")


def get_blocked_tiles(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    placeholders = ",".join("?" for _ in BLOCKING_TILE_TYPES)
    rows = conn.execute(
        f"SELECT x, y FROM world_tiles WHERE tile_type IN ({placeholders})",
        BLOCKING_TILE_TYPES,
    ).fetchall()
    return {(row["x"], row["y"]) for row in rows}


def list_all_tiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT x, y, tile_type, building_id FROM world_tiles").fetchall()
    return [dict(row) for row in rows]


def list_non_empty_tiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT x, y, tile_type, building_id FROM world_tiles WHERE tile_type != 'empty'"
    ).fetchall()
    return [dict(row) for row in rows]


def list_buildings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, type, x, y, owner_agent_id, status, construction_progress, "
        "construction_total_ticks, capacity FROM buildings"
    ).fetchall()
    return [dict(row) for row in rows]


def get_building(conn: sqlite3.Connection, building_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, type, x, y, owner_agent_id, status, construction_progress, "
        "construction_total_ticks, capacity FROM buildings WHERE id = ?",
        (building_id,),
    ).fetchone()
    return dict(row) if row else None


def get_tile_type(conn: sqlite3.Connection, x: int, y: int) -> str | None:
    row = conn.execute("SELECT tile_type FROM world_tiles WHERE x = ? AND y = ?", (x, y)).fetchone()
    return row["tile_type"] if row else None


def set_building_owner(conn: sqlite3.Connection, building_id: int, owner_agent_id: int) -> None:
    conn.execute("UPDATE buildings SET owner_agent_id = ? WHERE id = ?", (owner_agent_id, building_id))


def release_building_owner(conn: sqlite3.Connection, building_id: int) -> None:
    """Vacates a building (e.g. on the owner's death) so a newcomer can
    claim it later."""
    conn.execute("UPDATE buildings SET owner_agent_id = NULL WHERE id = ?", (building_id,))


def find_vacant_house(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT id, x, y FROM buildings WHERE type = 'house' AND status = 'complete' "
        "AND owner_agent_id IS NULL ORDER BY id LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def create_building_under_construction(
    conn: sqlite3.Connection,
    building_type: str,
    x: int,
    y: int,
    built_by_agent_id: int,
    owner_agent_id: int | None,
    construction_total_ticks: int,
    created_tick: int,
) -> int:
    cur = conn.execute(
        "INSERT INTO buildings "
        "(type, x, y, owner_agent_id, status, construction_progress, "
        "construction_total_ticks, built_by_agent_id, capacity, created_tick) "
        "VALUES (?, ?, ?, ?, 'under_construction', 0, ?, ?, NULL, ?)",
        (building_type, x, y, owner_agent_id, construction_total_ticks, built_by_agent_id, created_tick),
    )
    building_id = cur.lastrowid
    conn.execute(
        "INSERT INTO world_tiles (x, y, tile_type, building_id) VALUES (?, ?, 'under_construction', ?) "
        "ON CONFLICT(x, y) DO UPDATE SET tile_type = 'under_construction', building_id = excluded.building_id",
        (x, y, building_id),
    )
    return building_id


def list_under_construction_buildings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, type, x, y, owner_agent_id, built_by_agent_id, "
        "construction_progress, construction_total_ticks "
        "FROM buildings WHERE status = 'under_construction'"
    ).fetchall()
    return [dict(row) for row in rows]


def update_construction_progress(conn: sqlite3.Connection, building_id: int, progress: int) -> None:
    conn.execute("UPDATE buildings SET construction_progress = ? WHERE id = ?", (progress, building_id))


def complete_building(conn: sqlite3.Connection, building_id: int, x: int, y: int, building_type: str) -> None:
    conn.execute("UPDATE buildings SET status = 'complete' WHERE id = ?", (building_id,))
    conn.execute("UPDATE world_tiles SET tile_type = ? WHERE x = ? AND y = ?", (building_type, x, y))
