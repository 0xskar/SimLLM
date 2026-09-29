from __future__ import annotations

from simllm.db import memory_repo, save_repo


def make_conn(isolated_saves_dir):
    save_repo.create_save("memtest", population_target=1)
    return save_repo.load_save("memtest")


def test_add_and_list_all_memories_most_recent_first(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        agent_id = 1
        for i in range(3):
            memory_repo.add_memory(
                conn, agent_id=agent_id, tick=i, sim_datetime=f"t{i}", type="action", content=f"event {i}"
            )
        conn.commit()

        rows = memory_repo.list_all_memories(conn, agent_id)
        assert [r["content"] for r in rows] == ["event 2", "event 1", "event 0"]
    finally:
        conn.close()


def test_list_all_memories_pagination(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        agent_id = 1
        for i in range(5):
            memory_repo.add_memory(
                conn, agent_id=agent_id, tick=i, sim_datetime=f"t{i}", type="action", content=f"event {i}"
            )
        conn.commit()

        page1 = memory_repo.list_all_memories(conn, agent_id, limit=2, offset=0)
        page2 = memory_repo.list_all_memories(conn, agent_id, limit=2, offset=2)

        assert [r["content"] for r in page1] == ["event 4", "event 3"]
        assert [r["content"] for r in page2] == ["event 2", "event 1"]
    finally:
        conn.close()


def test_get_recent_memories_returns_chronological_oldest_first(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        agent_id = 1
        for i in range(5):
            memory_repo.add_memory(
                conn, agent_id=agent_id, tick=i, sim_datetime=f"t{i}", type="action", content=f"event {i}"
            )
        conn.commit()

        recent = memory_repo.get_recent_memories(conn, agent_id, limit=3)
        assert [r["content"] for r in recent] == ["event 2", "event 3", "event 4"]
    finally:
        conn.close()


def test_get_recent_memories_with_zero_limit_returns_empty(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        memory_repo.add_memory(conn, agent_id=1, tick=0, sim_datetime="t0", type="action", content="x")
        conn.commit()

        assert memory_repo.get_recent_memories(conn, 1, limit=0) == []
    finally:
        conn.close()


def test_get_memories_since_tick_excludes_tick_itself_and_earlier(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        agent_id = 1
        for i in range(5):
            memory_repo.add_memory(
                conn, agent_id=agent_id, tick=i, sim_datetime=f"t{i}", type="action", content=f"event {i}"
            )
        conn.commit()

        since = memory_repo.get_memories_since_tick(conn, agent_id, since_tick=2)
        assert [r["content"] for r in since] == ["event 3", "event 4"]
    finally:
        conn.close()


def test_memories_are_scoped_per_agent(isolated_saves_dir):
    save_repo.create_save("memtest2", population_target=2)
    conn = save_repo.load_save("memtest2")
    try:
        memory_repo.add_memory(conn, agent_id=1, tick=0, sim_datetime="t0", type="action", content="agent1 event")
        memory_repo.add_memory(conn, agent_id=2, tick=0, sim_datetime="t0", type="action", content="agent2 event")
        conn.commit()

        agent1_memories = memory_repo.list_all_memories(conn, 1)
        assert len(agent1_memories) == 1
        assert agent1_memories[0]["content"] == "agent1 event"
    finally:
        conn.close()
