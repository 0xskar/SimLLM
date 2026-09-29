from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

TickCallback = Callable[[], Awaitable[dict]]


class SimClock:
    """Drift-tolerant tick scheduler.

    Schedules the next tick relative to the previous tick's *completion*
    time rather than a fixed wall-clock cadence, so a slow tick (e.g. an
    agent's LLM call running long) never causes overlapping ticks.
    """

    def __init__(self, tick_interval_seconds: float, on_tick: TickCallback):
        self.tick_interval_seconds = tick_interval_seconds
        self.on_tick = on_tick
        self._task: asyncio.Task | None = None
        self._paused = True

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_interval(self, seconds: float) -> None:
        self.tick_interval_seconds = seconds

    def start(self) -> None:
        self._paused = False
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self.start()

    async def step(self) -> dict:
        """Run exactly one tick regardless of paused state (used while paused)."""
        return await self.on_tick()

    async def _run_loop(self) -> None:
        while not self._paused:
            start = time.monotonic()
            await self.on_tick()
            elapsed = time.monotonic() - start
            sleep_for = max(0.0, self.tick_interval_seconds - elapsed)
            await asyncio.sleep(sleep_for)

    async def shutdown(self) -> None:
        self._paused = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
