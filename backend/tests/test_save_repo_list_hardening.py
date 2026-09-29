from __future__ import annotations

from simllm.db import save_repo


def test_list_saves_returns_empty_when_saves_dir_missing(isolated_saves_dir):
    assert not isolated_saves_dir.exists()
    assert save_repo.list_saves() == []


def test_list_saves_skips_a_corrupt_file_and_still_lists_valid_saves(isolated_saves_dir):
    save_repo.create_save("goodsave", population_target=1)

    isolated_saves_dir.mkdir(parents=True, exist_ok=True)
    garbage_path = isolated_saves_dir / "corrupt.sqlite3"
    garbage_path.write_bytes(b"not a real sqlite database")

    saves = save_repo.list_saves()
    names = [s.name for s in saves]
    assert names == ["goodsave"]


def test_delete_save_removes_leftover_wal_and_shm_sidecars(isolated_saves_dir):
    save_repo.create_save("sidecartest", population_target=1)
    path = isolated_saves_dir / "sidecartest.sqlite3"

    wal = path.with_name(path.name + "-wal")
    shm = path.with_name(path.name + "-shm")
    wal.write_bytes(b"")
    shm.write_bytes(b"")

    save_repo.delete_save("sidecartest")

    assert not path.exists()
    assert not wal.exists()
    assert not shm.exists()
