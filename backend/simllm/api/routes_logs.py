from __future__ import annotations

from fastapi import APIRouter

from simllm.db import logs_repo
from simllm.state import app_state

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def get_logs(category: str | None = None, limit: int = 200, before_tick: int | None = None) -> list[dict]:
    """Historical backfill for the Logs panel (on load/reconnect) or manual
    pagination -- live updates after that arrive over the WS 'log' event,
    not repeated polling of this endpoint."""
    conn = app_state.require_conn()
    return logs_repo.list_events(conn, category=category, limit=limit, before_tick=before_tick)


@router.get("/categories")
def get_log_categories() -> list[str]:
    return logs_repo.LOG_CATEGORIES
