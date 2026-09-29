from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from simllm.api import routes_models
from simllm.main import app


class _FakeModel:
    def __init__(self, model: str, size: int, family: str | None):
        self.model = model
        self.size = size
        self.details = SimpleNamespace(family=family, parameter_size="7B") if family else None


class _FakeListResponse:
    def __init__(self, models):
        self.models = models


class _FakeOllamaClient:
    def __init__(self, host=None):
        self.host = host

    async def list(self):
        return _FakeListResponse(
            [
                _FakeModel("qwen2.5:7b-instruct", 123, "qwen2"),
                _FakeModel("mystery-model:1b", 456, "some-unrecommended-family"),
            ]
        )


class _FailingOllamaClient:
    def __init__(self, host=None):
        pass

    async def list(self):
        raise ConnectionRefusedError("no server")


def test_list_models_maps_response_and_flags_recommended(monkeypatch):
    monkeypatch.setattr(routes_models.ollama, "AsyncClient", _FakeOllamaClient)

    client = TestClient(app)
    response = client.get("/api/models")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    qwen = next(m for m in data if m["name"] == "qwen2.5:7b-instruct")
    assert qwen["recommended"] is True
    assert qwen["parameter_size"] == "7B"

    mystery = next(m for m in data if m["name"] == "mystery-model:1b")
    assert mystery["recommended"] is False


def test_list_models_returns_503_when_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(routes_models.ollama, "AsyncClient", _FailingOllamaClient)

    client = TestClient(app)
    response = client.get("/api/models")

    assert response.status_code == 503


def test_is_recommended_matches_known_families():
    assert routes_models._is_recommended("qwen2") is True
    assert routes_models._is_recommended("llama") is True
    assert routes_models._is_recommended("QWEN3") is True
    assert routes_models._is_recommended("gpt-oss") is False
    assert routes_models._is_recommended(None) is False
