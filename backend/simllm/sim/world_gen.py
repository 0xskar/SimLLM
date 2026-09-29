from __future__ import annotations

import sqlite3

from simllm.db import economy_repo
from simllm.models.settings import Settings


def generate_world(
    width: int, height: int, house_count: int, workplace_count: int
) -> tuple[list[dict], list[dict]]:
    """Pure layout generator: deterministic given the same inputs.

    Lays a road cross through the middle of the grid, then fills houses and
    workplaces into the remaining empty tiles in scan order. Returns
    (tile_rows, building_specs) with no DB access, so this is unit-testable
    without a connection.
    """
    tiles: dict[tuple[int, int], str] = {
        (x, y): "empty" for y in range(height) for x in range(width)
    }

    road_y = height // 2
    road_x = width // 2
    for x in range(width):
        tiles[(x, road_y)] = "road"
    for y in range(height):
        tiles[(road_x, y)] = "road"

    candidates = [
        (x, y) for y in range(height) for x in range(width) if tiles[(x, y)] == "empty"
    ]

    buildings: list[dict] = []

    def place(building_type: str, count: int, pool: list[tuple[int, int]]) -> int:
        placed = 0
        idx = 0
        while placed < count and idx < len(pool):
            x, y = pool[idx]
            idx += 1
            tiles[(x, y)] = building_type
            buildings.append({"type": building_type, "x": x, "y": y})
            placed += 1
        return idx

    consumed = place("house", house_count, candidates)
    place("workplace", workplace_count, candidates[consumed:])

    tile_rows = [{"x": x, "y": y, "tile_type": t} for (x, y), t in tiles.items()]
    return tile_rows, buildings


def seed_world(conn: sqlite3.Connection, settings: Settings) -> None:
    """Insert a generated starter layout into a freshly created save's DB."""
    house_count = max(1, settings.population_target)
    workplace_count = max(1, house_count // 4)

    tile_rows, building_specs = generate_world(
        settings.world_width, settings.world_height, house_count, workplace_count
    )

    building_id_by_pos: dict[tuple[int, int], int] = {}
    for spec in building_specs:
        cur = conn.execute(
            "INSERT INTO buildings "
            "(type, x, y, owner_agent_id, status, construction_progress, "
            "construction_total_ticks, built_by_agent_id, capacity, created_tick) "
            "VALUES (?, ?, ?, NULL, 'complete', 0, 0, NULL, NULL, 0)",
            (spec["type"], spec["x"], spec["y"]),
        )
        building_id = cur.lastrowid
        building_id_by_pos[(spec["x"], spec["y"])] = building_id

        if spec["type"] == "workplace":
            economy_repo.create_job(
                conn, building_id, "Worker", settings.default_job_wage, settings.job_slots_per_workplace
            )

    for row in tile_rows:
        building_id = building_id_by_pos.get((row["x"], row["y"]))
        conn.execute(
            "INSERT INTO world_tiles (x, y, tile_type, building_id) VALUES (?, ?, ?, ?)",
            (row["x"], row["y"], row["tile_type"], building_id),
        )
    conn.commit()
