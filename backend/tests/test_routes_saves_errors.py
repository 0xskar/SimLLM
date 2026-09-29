from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.db import save_repo
from simllm.main import app


def test_create_save_conflict_on_duplicate_name(isolated_saves_dir):
    client = TestClient(app)
    body = {"name": "saveroutedup", "population_target": 1}
    first = client.post("/api/saves", json=body)
    assert first.status_code == 201

    second = client.post("/api/saves", json=body)
    assert second.status_code == 409


def test_load_save_404_for_unknown_name(isolated_saves_dir):
    client = TestClient(app)
    response = client.post("/api/saves/does-not-exist/load")
    assert response.status_code == 404


def test_delete_save_404_for_unknown_name(isolated_saves_dir):
    client = TestClient(app)
    response = client.delete("/api/saves/does-not-exist")
    assert response.status_code == 404


def test_cannot_delete_the_currently_loaded_save(isolated_saves_dir):
    save_repo.create_save("saveroutecurrent", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/saveroutecurrent/load")

    response = client.delete("/api/saves/saveroutecurrent")
    assert response.status_code == 400


def test_delete_save_succeeds_for_an_unloaded_save(isolated_saves_dir):
    save_repo.create_save("saveroutecurrent2", population_target=1)
    save_repo.create_save("saveroutevictim", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/saveroutecurrent2/load")

    response = client.delete("/api/saves/saveroutevictim")
    assert response.status_code == 204

    names = [s["name"] for s in client.get("/api/saves").json()]
    assert "saveroutevictim" not in names
