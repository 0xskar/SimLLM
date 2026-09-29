from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.db import save_repo
from simllm.main import app


def test_get_world_returns_dimensions_tiles_and_buildings(isolated_saves_dir):
    save_repo.create_save("worldroutetest", population_target=1, world_width=10, world_height=8)
    client = TestClient(app)
    client.post("/api/saves/worldroutetest/load")

    response = client.get("/api/world")
    assert response.status_code == 200
    data = response.json()
    assert data["width"] == 10
    assert data["height"] == 8
    assert len(data["tiles"]) == 10 * 8
    # The starter agent's house from save creation should already be present.
    assert any(b["type"] == "house" for b in data["buildings"])
