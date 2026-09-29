from __future__ import annotations

from simllm.db import save_repo, world_repo


def make_conn(isolated_saves_dir, population_target=2):
    save_repo.create_save("wrctest", population_target=population_target, world_width=12, world_height=12)
    return save_repo.load_save("wrctest")


def find_empty_tile(conn) -> tuple[int, int]:
    row = conn.execute("SELECT x, y FROM world_tiles WHERE tile_type = 'empty' LIMIT 1").fetchone()
    return row["x"], row["y"]


def test_get_tile_type_returns_correct_type(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        house = conn.execute("SELECT x, y FROM buildings WHERE type = 'house' LIMIT 1").fetchone()
        assert world_repo.get_tile_type(conn, house["x"], house["y"]) == "house"

        x, y = find_empty_tile(conn)
        assert world_repo.get_tile_type(conn, x, y) == "empty"
    finally:
        conn.close()


def test_create_building_under_construction_sets_tile_and_building(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        x, y = find_empty_tile(conn)
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]

        building_id = world_repo.create_building_under_construction(
            conn, "house", x, y, agent_id, agent_id, construction_total_ticks=10, created_tick=5
        )
        conn.commit()

        assert world_repo.get_tile_type(conn, x, y) == "under_construction"
        building = world_repo.get_building(conn, building_id)
        assert building["status"] == "under_construction"
        assert building["construction_progress"] == 0
        assert building["construction_total_ticks"] == 10
        assert building["owner_agent_id"] == agent_id
    finally:
        conn.close()


def test_list_under_construction_buildings_only_returns_incomplete(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        x, y = find_empty_tile(conn)
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        world_repo.create_building_under_construction(conn, "house", x, y, agent_id, agent_id, 10, 0)
        conn.commit()

        under_construction = world_repo.list_under_construction_buildings(conn)
        assert len(under_construction) == 1
        assert under_construction[0]["type"] == "house"

        # Seeded (already-complete) buildings shouldn't show up.
        complete_count = conn.execute(
            "SELECT COUNT(*) AS c FROM buildings WHERE status = 'complete'"
        ).fetchone()["c"]
        assert complete_count > 0
    finally:
        conn.close()


def test_update_construction_progress_persists(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        x, y = find_empty_tile(conn)
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        building_id = world_repo.create_building_under_construction(conn, "house", x, y, agent_id, agent_id, 10, 0)
        conn.commit()

        world_repo.update_construction_progress(conn, building_id, 7)
        conn.commit()

        building = world_repo.get_building(conn, building_id)
        assert building["construction_progress"] == 7
    finally:
        conn.close()


def test_complete_building_flips_status_and_tile(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        x, y = find_empty_tile(conn)
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]
        building_id = world_repo.create_building_under_construction(conn, "workplace", x, y, agent_id, None, 10, 0)
        conn.commit()

        world_repo.complete_building(conn, building_id, x, y, "workplace")
        conn.commit()

        building = world_repo.get_building(conn, building_id)
        assert building["status"] == "complete"
        assert world_repo.get_tile_type(conn, x, y) == "workplace"
    finally:
        conn.close()


def test_set_building_owner(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        house = conn.execute("SELECT id FROM buildings WHERE type = 'house' LIMIT 1").fetchone()
        agent_id = conn.execute("SELECT id FROM agents LIMIT 1").fetchone()["id"]

        world_repo.set_building_owner(conn, house["id"], agent_id)
        conn.commit()

        building = world_repo.get_building(conn, house["id"])
        assert building["owner_agent_id"] == agent_id
    finally:
        conn.close()


def test_starter_agent_owns_their_seeded_house(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir, population_target=3)
    try:
        agents = conn.execute("SELECT id, home_building_id FROM agents").fetchall()
        for agent in agents:
            building = world_repo.get_building(conn, agent["home_building_id"])
            assert building["owner_agent_id"] == agent["id"]
    finally:
        conn.close()


def test_release_building_owner_vacates_it(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir, population_target=1)
    try:
        house = conn.execute("SELECT id FROM buildings WHERE type = 'house' LIMIT 1").fetchone()
        assert world_repo.get_building(conn, house["id"])["owner_agent_id"] is not None

        world_repo.release_building_owner(conn, house["id"])
        conn.commit()

        assert world_repo.get_building(conn, house["id"])["owner_agent_id"] is None
    finally:
        conn.close()


def test_find_vacant_house_returns_none_when_all_owned(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir, population_target=2)
    try:
        assert world_repo.find_vacant_house(conn) is None
    finally:
        conn.close()


def test_find_vacant_house_finds_a_released_house(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir, population_target=2)
    try:
        house = conn.execute("SELECT id, x, y FROM buildings WHERE type = 'house' LIMIT 1").fetchone()
        world_repo.release_building_owner(conn, house["id"])
        conn.commit()

        vacant = world_repo.find_vacant_house(conn)
        assert vacant["id"] == house["id"]
    finally:
        conn.close()
