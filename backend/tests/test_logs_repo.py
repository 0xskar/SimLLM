from __future__ import annotations

from simllm.db import logs_repo, save_repo


def make_conn(isolated_saves_dir):
    save_repo.create_save("logstest", population_target=1)
    return save_repo.load_save("logstest")


def test_add_and_list_events_most_recent_first(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        for i in range(3):
            logs_repo.add_event(
                conn, tick=i, sim_datetime=f"t{i}", category="llm_call", agent_id=1,
                payload={"level": "info", "message": f"event {i}"},
            )
        conn.commit()

        events = logs_repo.list_events(conn)
        assert [e["message"] for e in events] == ["event 2", "event 1", "event 0"]
    finally:
        conn.close()


def test_list_events_filters_by_category(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        logs_repo.add_event(conn, tick=0, sim_datetime="t0", category="death", agent_id=1, payload={"level": "warning", "message": "died"})
        logs_repo.add_event(conn, tick=1, sim_datetime="t1", category="llm_call", agent_id=1, payload={"level": "info", "message": "decided"})
        conn.commit()

        death_events = logs_repo.list_events(conn, category="death")
        assert len(death_events) == 1
        assert death_events[0]["message"] == "died"
    finally:
        conn.close()


def test_list_events_respects_limit(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        for i in range(5):
            logs_repo.add_event(conn, tick=i, sim_datetime=f"t{i}", category="system", agent_id=None, payload={"level": "info", "message": f"e{i}"})
        conn.commit()

        events = logs_repo.list_events(conn, limit=2)
        assert len(events) == 2
        assert events[0]["message"] == "e4"
    finally:
        conn.close()


def test_list_events_before_tick_pagination(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        for i in range(5):
            logs_repo.add_event(conn, tick=i, sim_datetime=f"t{i}", category="system", agent_id=None, payload={"level": "info", "message": f"e{i}"})
        conn.commit()

        events = logs_repo.list_events(conn, before_tick=3)
        assert [e["message"] for e in events] == ["e2", "e1", "e0"]
    finally:
        conn.close()


def test_list_events_preserves_extra_payload_fields(isolated_saves_dir):
    conn = make_conn(isolated_saves_dir)
    try:
        logs_repo.add_event(
            conn, tick=0, sim_datetime="t0", category="conversation", agent_id=1,
            payload={"level": "info", "message": "talked", "agent_b_id": 2, "transcript": ["a: hi", "b: hi"]},
        )
        conn.commit()

        events = logs_repo.list_events(conn)
        assert events[0]["agent_b_id"] == 2
        assert events[0]["transcript"] == ["a: hi", "b: hi"]
    finally:
        conn.close()
