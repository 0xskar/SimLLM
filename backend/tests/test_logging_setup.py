from __future__ import annotations

from simllm.db import logs_repo, save_repo
from simllm.logging_setup import record_log_event


async def test_record_log_event_writes_to_db_and_broadcasts(isolated_saves_dir):
    save_repo.create_save("recordtest", population_target=1)
    conn = save_repo.load_save("recordtest")
    try:
        broadcasts = []

        async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
            broadcasts.append((event_type, payload, tick, sim_time))

        await record_log_event(
            conn, None, fake_broadcast,
            category="llm_call", level="info", message="Alex chose eat.",
            tick=5, sim_time="2000-01-01T06:00:00", agent_id=1, action="eat",
        )
        conn.commit()

        events = logs_repo.list_events(conn)
        assert len(events) == 1
        assert events[0]["message"] == "Alex chose eat."
        assert events[0]["agent_id"] == 1
        assert events[0]["action"] == "eat"

        assert len(broadcasts) == 1
        event_type, payload, tick, sim_time = broadcasts[0]
        assert event_type == "log"
        assert payload["category"] == "llm_call"
        assert payload["message"] == "Alex chose eat."
        assert tick == 5
    finally:
        conn.close()


async def test_record_log_event_handles_none_conn_logger_and_broadcast(isolated_saves_dir):
    # Should never raise even with nothing configured -- logging must never
    # be the thing that breaks a tick.
    await record_log_event(
        None, None, None,
        category="system", level="info", message="noop", tick=0, sim_time="t0",
    )


async def test_record_log_event_skips_db_write_when_conn_is_none():
    calls = []

    async def fake_broadcast(event_type, payload, tick=None, sim_time=None):
        calls.append(payload)

    # No exception, and the broadcast still happens even without a DB.
    await record_log_event(
        None, None, fake_broadcast,
        category="system", level="info", message="hello", tick=0, sim_time="t0",
    )
    assert len(calls) == 1
