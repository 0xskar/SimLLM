from __future__ import annotations

import pytest

from simllm.db import save_repo


def test_create_and_list_save(isolated_saves_dir):
    save_repo.create_save("alpha", world_width=10, world_height=10, population_target=5)

    saves = save_repo.list_saves()
    assert len(saves) == 1
    assert saves[0].name == "alpha"
    assert saves[0].current_tick == 0
    assert saves[0].generation == 1
    assert saves[0].population == 5  # one starter agent per seeded house


def test_create_duplicate_save_raises(isolated_saves_dir):
    save_repo.create_save("alpha")
    with pytest.raises(save_repo.SaveAlreadyExistsError):
        save_repo.create_save("alpha")


def test_load_settings_reflects_overrides(isolated_saves_dir):
    save_repo.create_save("beta", world_width=42, world_height=17, population_target=3)

    conn = save_repo.load_save("beta")
    try:
        settings = save_repo.load_settings(conn)
        assert settings.world_width == 42
        assert settings.world_height == 17
        assert settings.population_target == 3
        # untouched defaults still come through the merge
        assert settings.ollama_model
    finally:
        conn.close()


def test_load_missing_save_raises(isolated_saves_dir):
    with pytest.raises(save_repo.SaveNotFoundError):
        save_repo.load_save("does-not-exist")


def test_delete_save_removes_file(isolated_saves_dir):
    save_repo.create_save("gamma")
    assert len(save_repo.list_saves()) == 1

    save_repo.delete_save("gamma")
    assert len(save_repo.list_saves()) == 0


def test_save_settings_persists_changes(isolated_saves_dir):
    save_repo.create_save("delta")
    conn = save_repo.load_save("delta")
    try:
        settings = save_repo.load_settings(conn)
        settings.population_target = 99
        save_repo.save_settings(conn, settings)

        reloaded = save_repo.load_settings(conn)
        assert reloaded.population_target == 99
    finally:
        conn.close()
