from __future__ import annotations

from simllm.db import save_repo
from simllm.sim.world_gen import generate_world


def test_tile_rows_cover_full_grid_exactly_once():
    tiles, _ = generate_world(width=10, height=8, house_count=3, workplace_count=1)

    assert len(tiles) == 10 * 8
    positions = {(t["x"], t["y"]) for t in tiles}
    assert len(positions) == 10 * 8
    for t in tiles:
        assert 0 <= t["x"] < 10
        assert 0 <= t["y"] < 8


def test_road_cross_is_placed():
    tiles, _ = generate_world(width=10, height=8, house_count=0, workplace_count=0)

    by_pos = {(t["x"], t["y"]): t["tile_type"] for t in tiles}
    road_y, road_x = 8 // 2, 10 // 2
    assert all(by_pos[(x, road_y)] == "road" for x in range(10))
    assert all(by_pos[(road_x, y)] == "road" for y in range(8))


def test_requested_building_counts_are_placed():
    tiles, buildings = generate_world(width=12, height=12, house_count=4, workplace_count=2)

    houses = [b for b in buildings if b["type"] == "house"]
    workplaces = [b for b in buildings if b["type"] == "workplace"]
    assert len(houses) == 4
    assert len(workplaces) == 2

    by_pos = {(t["x"], t["y"]): t["tile_type"] for t in tiles}
    for b in buildings:
        assert by_pos[(b["x"], b["y"])] == b["type"]


def test_buildings_never_overlap_each_other_or_roads():
    tiles, buildings = generate_world(width=10, height=10, house_count=8, workplace_count=4)

    positions = [(b["x"], b["y"]) for b in buildings]
    assert len(positions) == len(set(positions))

    by_pos = {(t["x"], t["y"]): t["tile_type"] for t in tiles}
    road_positions = {pos for pos, t in by_pos.items() if t == "road"}
    assert not (set(positions) & road_positions)


def test_requesting_more_buildings_than_space_does_not_crash():
    # Grid has far fewer empty tiles than requested houses; should place as
    # many as fit without raising, never overlapping.
    tiles, buildings = generate_world(width=3, height=3, house_count=50, workplace_count=50)

    positions = [(b["x"], b["y"]) for b in buildings]
    assert len(positions) == len(set(positions))
    assert len(buildings) <= 3 * 3


def test_seed_world_creates_one_job_per_workplace(isolated_saves_dir):
    save_repo.create_save("jobseed", population_target=8, world_width=16, world_height=16)
    conn = save_repo.load_save("jobseed")
    try:
        workplace_count = conn.execute(
            "SELECT COUNT(*) AS c FROM buildings WHERE type = 'workplace'"
        ).fetchone()["c"]
        job_count = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]

        assert workplace_count > 0
        assert job_count == workplace_count
    finally:
        conn.close()
