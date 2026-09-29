from __future__ import annotations

from fastapi import APIRouter, HTTPException

from simllm.db import agents_repo, economy_repo, memory_repo, relationships_repo, world_repo
from simllm.state import app_state

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents() -> list[dict]:
    conn = app_state.require_conn()
    return agents_repo.list_agent_summaries(conn)


@router.get("/{agent_id}")
def get_agent(agent_id: int) -> dict:
    conn = app_state.require_conn()
    detail = agents_repo.get_agent_detail(conn, agent_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    detail["current_job"] = economy_repo.get_active_assignment(conn, agent_id)
    detail["home_building"] = (
        world_repo.get_building(conn, detail["home_building_id"])
        if detail["home_building_id"] is not None
        else None
    )
    return detail


@router.get("/{agent_id}/memories")
def get_agent_memories(agent_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
    conn = app_state.require_conn()
    return memory_repo.list_all_memories(conn, agent_id, limit=limit, offset=offset)


@router.get("/{agent_id}/relationships")
def get_agent_relationships(agent_id: int) -> list[dict]:
    conn = app_state.require_conn()
    return relationships_repo.list_relationships_for_agent(conn, agent_id)
