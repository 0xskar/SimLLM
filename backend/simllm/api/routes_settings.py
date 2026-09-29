from __future__ import annotations

from fastapi import APIRouter

from simllm.db import save_repo
from simllm.models.settings import Settings
from simllm.state import app_state

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings() -> dict:
    return app_state.require_settings().model_dump()


@router.put("")
def update_settings(overrides: dict) -> dict:
    current = app_state.require_settings().model_dump()
    current.update(overrides)
    settings = Settings.model_validate(current)

    conn = app_state.require_conn()
    save_repo.save_settings(conn, settings)
    app_state.update_settings(settings)

    return settings.model_dump()
