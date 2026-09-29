from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.db import save_repo
from simllm.main import app


def test_get_settings_returns_current_values(isolated_saves_dir):
    save_repo.create_save("settingsroutetest", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/settingsroutetest/load")

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["population_target"] == 1


def test_put_settings_persists_and_returns_overrides(isolated_saves_dir):
    save_repo.create_save("settingsroutetest2", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/settingsroutetest2/load")

    response = client.put("/api/settings", json={"worker_concurrency": 9})
    assert response.status_code == 200
    assert response.json()["worker_concurrency"] == 9

    # Persisted, not just held in memory for this request.
    refetched = client.get("/api/settings").json()
    assert refetched["worker_concurrency"] == 9
