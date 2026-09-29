from __future__ import annotations

import ollama
from fastapi import APIRouter, HTTPException

from simllm.config import default_settings
from simllm.state import app_state

router = APIRouter(prefix="/api/models", tags=["models"])

# Model families we've found reliably support Ollama tool-calling -- used
# only to flag a sensible default in the UI, never to filter the list (any
# installed model can still be picked).
RECOMMENDED_FAMILIES = {"qwen", "qwen2", "qwen3", "llama", "mistral", "firefunction", "command-r"}


def _is_recommended(family: str | None) -> bool:
    if not family:
        return False
    return family.lower() in RECOMMENDED_FAMILIES


@router.get("")
async def list_models() -> list[dict]:
    settings = app_state.settings or default_settings()
    client = ollama.AsyncClient(host=settings.ollama_host)

    try:
        response = await client.list()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not reach Ollama at {settings.ollama_host}: {exc}") from exc

    models = []
    for m in response.models:
        family = m.details.family if m.details else None
        models.append(
            {
                "name": m.model,
                "size": m.size,
                "parameter_size": m.details.parameter_size if m.details else None,
                "family": family,
                "recommended": _is_recommended(family),
            }
        )
    return models
