from __future__ import annotations

from fastapi import APIRouter, HTTPException

from simllm.api.ws import manager
from simllm.db import save_repo
from simllm.logging_setup import record_log_event
from simllm.state import app_state

router = APIRouter(prefix="/api/sim", tags=["sim"])


def _require_clock():
    if app_state.clock is None:
        raise HTTPException(status_code=400, detail="No save is currently loaded")
    return app_state.clock


def _persist_pause_state(paused: bool) -> None:
    conn = app_state.require_conn()
    conn.execute("UPDATE sim_clock SET is_paused = ? WHERE id = 1", (1 if paused else 0,))
    conn.commit()


async def _log_system_event(message: str) -> None:
    conn = app_state.require_conn()
    row = conn.execute("SELECT current_tick, sim_datetime FROM sim_clock WHERE id = 1").fetchone()
    await record_log_event(
        conn, app_state.logger, manager.broadcast,
        category="system", level="info", message=message,
        tick=row["current_tick"], sim_time=row["sim_datetime"],
    )
    conn.commit()


@router.get("/status")
def status() -> dict:
    conn = app_state.require_conn()
    row = conn.execute(
        "SELECT current_tick, sim_datetime, is_paused, generation, last_saved_at FROM sim_clock WHERE id = 1"
    ).fetchone()
    population = conn.execute(
        "SELECT COUNT(*) AS c FROM agents WHERE is_alive = 1"
    ).fetchone()["c"]
    return {
        "tick": row["current_tick"],
        "sim_time": row["sim_datetime"],
        "is_paused": bool(row["is_paused"]),
        "generation": row["generation"],
        "population": population,
        "save_name": app_state.save_name,
        "last_saved_at": row["last_saved_at"],
    }


@router.post("/start")
async def start_sim() -> dict:
    # Must run on the event loop thread: SimClock.start() calls
    # asyncio.create_task, which requires a running loop. A plain `def`
    # route would run in FastAPI's worker threadpool instead, which has none.
    _require_clock().start()
    _persist_pause_state(False)
    await _log_system_event(f"Simulation started ({app_state.save_name}).")
    return status()


@router.post("/pause")
async def pause_sim() -> dict:
    _require_clock().pause()
    _persist_pause_state(True)

    # Pausing is a natural save point for the user -- make sure the WAL is
    # flushed into the main file rather than waiting for the next autosave.
    conn = app_state.require_conn()
    save_repo.touch_last_saved(conn)
    conn.commit()
    save_repo.checkpoint(conn)

    await _log_system_event("Simulation paused.")
    return status()


@router.post("/resume")
async def resume_sim() -> dict:
    _require_clock().resume()
    _persist_pause_state(False)
    await _log_system_event("Simulation resumed.")
    return status()


@router.post("/step")
async def step_sim() -> dict:
    clock = _require_clock()
    if not clock.is_paused:
        raise HTTPException(status_code=400, detail="Pause the simulation before stepping")
    return await clock.step()
