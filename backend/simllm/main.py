from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from simllm.api import (
    routes_agents,
    routes_logs,
    routes_models,
    routes_saves,
    routes_settings,
    routes_sim,
    routes_world,
    ws,
)
from simllm.config import FRONTEND_DIST_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="SimLLM")

    app.include_router(routes_saves.router)
    app.include_router(routes_sim.router)
    app.include_router(routes_world.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_agents.router)
    app.include_router(routes_models.router)
    app.include_router(routes_logs.router)
    app.include_router(ws.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    if FRONTEND_DIST_DIR.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")

    return app


app = create_app()
