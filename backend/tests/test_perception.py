from __future__ import annotations

from simllm.sim.perception import (
    get_local_perception,
    get_nearby_agents,
    get_nearby_buildings,
    get_nearby_jobs,
    get_nearby_tiles,
)


def test_get_nearby_tiles_excludes_empty_tiles():
    tiles = [
        {"x": 0, "y": 0, "tile_type": "empty"},
        {"x": 1, "y": 0, "tile_type": "road"},
    ]

    result = get_nearby_tiles(tiles, x=0, y=0, radius=5)

    assert result == [{"x": 1, "y": 0, "tile_type": "road"}]


def test_get_nearby_tiles_respects_chebyshev_radius_boundary():
    tiles = [
        {"x": 2, "y": 2, "tile_type": "road"},  # distance 2, inside radius=2
        {"x": 3, "y": 0, "tile_type": "road"},  # distance 3, outside radius=2
    ]

    result = get_nearby_tiles(tiles, x=0, y=0, radius=2)

    assert result == [{"x": 2, "y": 2, "tile_type": "road"}]


def test_get_nearby_buildings_filters_by_radius():
    buildings = [
        {"id": 1, "type": "house", "x": 1, "y": 1},
        {"id": 2, "type": "workplace", "x": 10, "y": 10},
    ]

    result = get_nearby_buildings(buildings, x=0, y=0, radius=3)

    assert [b["id"] for b in result] == [1]


def test_get_nearby_agents_excludes_self():
    agents = [
        {"id": 1, "name": "Alex", "x": 0, "y": 0},
        {"id": 2, "name": "Bailey", "x": 1, "y": 0},
    ]

    result = get_nearby_agents(agents, self_id=1, x=0, y=0, radius=5)

    assert [a["id"] for a in result] == [2]


def test_get_nearby_agents_respects_radius():
    agents = [
        {"id": 2, "name": "Bailey", "x": 5, "y": 5},
        {"id": 3, "name": "Casey", "x": 0, "y": 1},
    ]

    result = get_nearby_agents(agents, self_id=1, x=0, y=0, radius=1)

    assert [a["id"] for a in result] == [3]


def test_get_nearby_jobs_filters_by_workplace_position():
    jobs = [
        {"id": 1, "title": "Worker", "x": 1, "y": 1},
        {"id": 2, "title": "Worker", "x": 20, "y": 20},
    ]

    result = get_nearby_jobs(jobs, x=0, y=0, radius=2)

    assert [j["id"] for j in result] == [1]


def test_get_local_perception_bundles_everything_and_filters_consistently():
    tiles = [{"x": 0, "y": 0, "tile_type": "empty"}, {"x": 1, "y": 0, "tile_type": "road"}]
    buildings = [{"id": 1, "type": "house", "x": 1, "y": 1}, {"id": 2, "type": "house", "x": 20, "y": 20}]
    agents = [
        {"id": 2, "name": "Bailey", "x": 1, "y": 1},
        {"id": 3, "name": "Casey", "x": 20, "y": 20},
    ]
    jobs = [
        {"id": 10, "title": "Worker", "x": 1, "y": 1},
        {"id": 11, "title": "Worker", "x": 20, "y": 20},
    ]

    perception = get_local_perception(tiles, buildings, agents, jobs, self_id=1, x=0, y=0, radius=2)

    assert perception["tiles"] == [{"x": 1, "y": 0, "tile_type": "road"}]
    assert [b["id"] for b in perception["buildings"]] == [1]
    assert [a["id"] for a in perception["agents"]] == [2]
    assert [j["id"] for j in perception["jobs"]] == [10]
