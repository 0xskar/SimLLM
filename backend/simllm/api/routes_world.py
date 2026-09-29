from __future__ import annotations

from fastapi import APIRouter

from simllm.db import world_repo
from simllm.state import app_state

router = APIRouter(prefix="/api/world", tags=["world"])


@router.get("")
def get_world() -> dict:
    conn = app_state.require_conn()
    settings = app_state.require_settings()
    return {
        "width": settings.world_width,
        "height": settings.world_height,
        "tiles": world_repo.list_all_tiles(conn),
        "buildings": world_repo.list_buildings(conn),
    }
