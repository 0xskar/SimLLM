from __future__ import annotations

from simllm.db import relationships_repo, save_repo


def make_conn(isolated_saves_dir):
    save_repo.create_save("reltest", population_target=3)
    return save_repo.load_save("reltest")


def test_get_relationship_returns_none_when_absent(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        assert relationships_repo.get_relationship(conn, 1, 2) is None
    finally:
        conn.close()


def test_upsert_and_get_relationship_order_independent(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        relationships_repo.upsert_relationship(conn, 1, 2, affinity=15.0, note="Friendly.", tick=5)
        conn.commit()

        forward = relationships_repo.get_relationship(conn, 1, 2)
        backward = relationships_repo.get_relationship(conn, 2, 1)

        assert forward == backward
        assert forward["affinity"] == 15.0
        assert forward["note"] == "Friendly."
    finally:
        conn.close()


def test_upsert_updates_existing_row_not_insert_duplicate(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        relationships_repo.upsert_relationship(conn, 1, 2, affinity=10.0, note="Met once.", tick=1)
        relationships_repo.upsert_relationship(conn, 2, 1, affinity=25.0, note="Good friends now.", tick=10)
        conn.commit()

        rel = relationships_repo.get_relationship(conn, 1, 2)
        assert rel["affinity"] == 25.0
        assert rel["note"] == "Good friends now."
        assert rel["updated_tick"] == 10

        count = conn.execute("SELECT COUNT(*) AS c FROM relationships").fetchone()["c"]
        assert count == 1
    finally:
        conn.close()


def test_list_relationships_for_agent_includes_other_agent_details(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        relationships_repo.upsert_relationship(conn, 1, 2, affinity=20.0, note="Buddies.", tick=1)
        relationships_repo.upsert_relationship(conn, 1, 3, affinity=-10.0, note="Rivals.", tick=2)
        conn.commit()

        rels = relationships_repo.list_relationships_for_agent(conn, 1)
        assert len(rels) == 2
        others = {r["other_agent_id"] for r in rels}
        assert others == {2, 3}
        for r in rels:
            assert r["other_name"]
            assert r["other_emoji"]
    finally:
        conn.close()


def test_clamp_affinity_bounds():
    assert relationships_repo.clamp_affinity(150.0) == 100.0
    assert relationships_repo.clamp_affinity(-150.0) == -100.0
    assert relationships_repo.clamp_affinity(42.0) == 42.0
