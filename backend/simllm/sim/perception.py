"""Local perception: what an agent can currently see, filtered to a radius
around their position. Pure functions operating on pre-fetched snapshots
(tiles/buildings/agents/jobs already queried from the DB once per tick) so
this is fully testable with fabricated world state -- no DB access needed.
"""
from __future__ import annotations


def _in_radius(ax: int, ay: int, bx: int, by: int, radius: int) -> bool:
    return max(abs(ax - bx), abs(ay - by)) <= radius


def get_nearby_tiles(tiles: list[dict], x: int, y: int, radius: int) -> list[dict]:
    """Non-empty tiles within radius (empty tiles aren't worth reporting)."""
    return [t for t in tiles if t["tile_type"] != "empty" and _in_radius(x, y, t["x"], t["y"], radius)]


def get_nearby_buildings(buildings: list[dict], x: int, y: int, radius: int) -> list[dict]:
    return [b for b in buildings if _in_radius(x, y, b["x"], b["y"], radius)]


def get_nearby_agents(agents: list[dict], self_id: int, x: int, y: int, radius: int) -> list[dict]:
    """Other alive agents within radius, excluding self."""
    return [a for a in agents if a["id"] != self_id and _in_radius(x, y, a["x"], a["y"], radius)]


def get_nearby_jobs(jobs: list[dict], x: int, y: int, radius: int) -> list[dict]:
    """Jobs whose workplace (already joined with x/y) is within radius."""
    return [j for j in jobs if _in_radius(x, y, j["x"], j["y"], radius)]


def get_local_perception(
    tiles: list[dict],
    buildings: list[dict],
    agents: list[dict],
    jobs: list[dict],
    self_id: int,
    x: int,
    y: int,
    radius: int,
) -> dict:
    """Bundle of everything an agent can currently perceive, radius-filtered
    from full snapshots fetched once per tick (shared across every due
    agent's perception this tick -- positions don't change again until the
    next tick's batch pass)."""
    return {
        "tiles": get_nearby_tiles(tiles, x, y, radius),
        "buildings": get_nearby_buildings(buildings, x, y, radius),
        "agents": get_nearby_agents(agents, self_id, x, y, radius),
        "jobs": get_nearby_jobs(jobs, x, y, radius),
    }
