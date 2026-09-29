from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from simllm.api.ws import manager
from simllm.db import save_repo
from simllm.logging_setup import record_log_event
from simllm.state import app_state

router = APIRouter(prefix="/api/saves", tags=["saves"])


class CreateSaveRequest(BaseModel):
    name: str
    world_width: int | None = None
    world_height: int | None = None
    population_target: int | None = None


class SaveSummaryResponse(BaseModel):
    name: str
    created_at: str
    current_tick: int
    generation: int
    population: int
    last_saved_at: str | None


@router.get("", response_model=list[SaveSummaryResponse])
def list_saves() -> list[SaveSummaryResponse]:
    return [SaveSummaryResponse(**s.__dict__) for s in save_repo.list_saves()]


@router.post("", response_model=SaveSummaryResponse, status_code=201)
def create_save(req: CreateSaveRequest) -> SaveSummaryResponse:
    try:
        save_repo.create_save(
            req.name,
            world_width=req.world_width,
            world_height=req.world_height,
            population_target=req.population_target,
        )
    except save_repo.SaveAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    summaries = {s.name: s for s in save_repo.list_saves()}
    return SaveSummaryResponse(**summaries[req.name].__dict__)


@router.post("/{name}/load", response_model=SaveSummaryResponse)
async def load_save(name: str) -> SaveSummaryResponse:
    try:
        conn = save_repo.load_save(name)
    except save_repo.SaveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    settings = save_repo.load_settings(conn)
    app_state.bind(name, conn, settings, manager.broadcast)

    row = conn.execute("SELECT current_tick, sim_datetime FROM sim_clock WHERE id = 1").fetchone()
    await record_log_event(
        conn, app_state.logger, manager.broadcast,
        category="system", level="info", message=f"Save '{name}' loaded.",
        tick=row["current_tick"], sim_time=row["sim_datetime"],
    )
    conn.commit()

    summaries = {s.name: s for s in save_repo.list_saves()}
    return SaveSummaryResponse(**summaries[name].__dict__)


@router.delete("/{name}", status_code=204)
def delete_save(name: str) -> None:
    if app_state.save_name == name:
        raise HTTPException(status_code=400, detail="Cannot delete the currently loaded save")
    try:
        save_repo.delete_save(name)
    except save_repo.SaveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
