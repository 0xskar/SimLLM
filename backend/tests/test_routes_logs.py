from __future__ import annotations

from fastapi.testclient import TestClient

from simllm.db import logs_repo, save_repo
from simllm.main import app


def test_get_logs_returns_persisted_events(isolated_saves_dir):
    save_repo.create_save("routelogtest", population_target=1)
    conn = save_repo.load_save("routelogtest")
    logs_repo.add_event(conn, tick=1, sim_datetime="t1", category="death", agent_id=1, payload={"level": "warning", "message": "Alex died."})
    conn.commit()
    conn.close()

    client = TestClient(app)
    client.post("/api/saves/routelogtest/load")

    response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert any(e["message"] == "Alex died." for e in data)


def test_get_logs_filters_by_category(isolated_saves_dir):
    save_repo.create_save("routelogtest2", population_target=1)
    conn = save_repo.load_save("routelogtest2")
    logs_repo.add_event(conn, tick=1, sim_datetime="t1", category="death", agent_id=1, payload={"level": "warning", "message": "died"})
    logs_repo.add_event(conn, tick=2, sim_datetime="t2", category="llm_call", agent_id=1, payload={"level": "info", "message": "decided"})
    conn.commit()
    conn.close()

    client = TestClient(app)
    client.post("/api/saves/routelogtest2/load")

    response = client.get("/api/logs", params={"category": "death"})
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "death"


def test_get_log_categories_returns_known_list():
    client = TestClient(app)
    response = client.get("/api/logs/categories")
    assert response.status_code == 200
    assert "llm_call" in response.json()
    assert "system" in response.json()
