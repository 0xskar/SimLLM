from __future__ import annotations

from simllm.db import save_repo


def test_new_save_has_no_last_saved_at(isolated_saves_dir):
    save_repo.create_save("autosavetest", population_target=1)

    saves = save_repo.list_saves()
    assert saves[0].last_saved_at is None


def test_touch_last_saved_sets_a_timestamp(isolated_saves_dir):
    save_repo.create_save("autosavetest2", population_target=1)
    conn = save_repo.load_save("autosavetest2")
    try:
        assert save_repo.list_saves()[0].last_saved_at is None

        timestamp = save_repo.touch_last_saved(conn)
        conn.commit()

        assert timestamp is not None
        saves = {s.name: s for s in save_repo.list_saves()}
        assert saves["autosavetest2"].last_saved_at == timestamp
    finally:
        conn.close()


def test_checkpoint_does_not_raise(isolated_saves_dir):
    save_repo.create_save("autosavetest3", population_target=1)
    conn = save_repo.load_save("autosavetest3")
    try:
        save_repo.checkpoint(conn)  # should complete without error
    finally:
        conn.close()
