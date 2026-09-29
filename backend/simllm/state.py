from __future__ import annotations

import logging
import sqlite3
from typing import Awaitable, Callable

from simllm.config import LOGS_DIR
from simllm.logging_setup import configure_logging
from simllm.models.settings import Settings
from simllm.sim.clock import SimClock
from simllm.sim.engine import SimulationEngine

BroadcastFn = Callable[..., Awaitable[None]]


class AppState:
    """Process-wide handle to whichever save is currently loaded.

    A single SimLLM backend process operates on one active save at a time.
    """

    def __init__(self) -> None:
        self.save_name: str | None = None
        self.conn: sqlite3.Connection | None = None
        self.settings: Settings | None = None
        self.engine: SimulationEngine | None = None
        self.clock: SimClock | None = None
        self.logger: logging.Logger | None = None

    def bind(
        self,
        save_name: str,
        conn: sqlite3.Connection,
        settings: Settings,
        broadcast_fn: BroadcastFn,
    ) -> None:
        if self.clock is not None:
            self.clock.pause()
        if self.conn is not None:
            self.conn.close()

        self.save_name = save_name
        self.conn = conn
        self.settings = settings
        self.logger = configure_logging(LOGS_DIR / save_name, save_name)
        self.engine = SimulationEngine(conn, settings, broadcast_fn, self.logger)

        engine = self.engine

        async def on_tick() -> dict:
            result = await engine.run_tick()
            await broadcast_fn(
                "tick_complete", result, tick=result["tick"], sim_time=result["sim_time"]
            )
            return result

        self.clock = SimClock(settings.tick_interval_seconds, on_tick)

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        if self.engine is not None:
            self.engine.settings = settings
        if self.clock is not None:
            self.clock.set_interval(settings.tick_interval_seconds)

    def require_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("No save is currently loaded")
        return self.conn

    def require_settings(self) -> Settings:
        if self.settings is None:
            raise RuntimeError("No save is currently loaded")
        return self.settings


app_state = AppState()
