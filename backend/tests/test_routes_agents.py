from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.db import save_repo
from simllm.main import app


def test_list_agents_returns_starter_population(isolated_saves_dir):
    save_repo.create_save("agentroutetest", population_target=2)
    client = TestClient(app)
    client.post("/api/saves/agentroutetest/load")

    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 2
    assert {"id", "name", "emoji", "x", "y", "is_alive"} <= agents[0].keys()


def test_get_agent_includes_job_and_home_building(isolated_saves_dir):
    save_repo.create_save("agentroutetest2", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/agentroutetest2/load")

    agent_id = client.get("/api/agents").json()[0]["id"]
    response = client.get(f"/api/agents/{agent_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == agent_id
    assert "current_job" in detail
    assert "home_building" in detail
    # The starter agent is spawned already owning a house (Milestone 11).
    assert detail["home_building"] is not None
    assert detail["home_building"]["type"] == "house"


def test_get_agent_404_for_unknown_id(isolated_saves_dir):
    save_repo.create_save("agentroutetest3", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/agentroutetest3/load")

    response = client.get("/api/agents/99999")
    assert response.status_code == 404


def test_get_agent_memories_and_relationships_start_empty(isolated_saves_dir):
    save_repo.create_save("agentroutetest4", population_target=1)
    client = TestClient(app)
    client.post("/api/saves/agentroutetest4/load")

    agent_id = client.get("/api/agents").json()[0]["id"]

    memories = client.get(f"/api/agents/{agent_id}/memories")
    assert memories.status_code == 200
    assert memories.json() == []

    relationships = client.get(f"/api/agents/{agent_id}/relationships")
    assert relationships.status_code == 200
    assert relationships.json() == []
