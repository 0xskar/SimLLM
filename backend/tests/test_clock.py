from __future__ import annotations

import asyncio


async def test_step_runs_tick_exactly_once():
    calls = []

    async def on_tick():
        calls.append(1)
        return {"tick": len(calls)}

    from simllm.sim.clock import SimClock

    clock = SimClock(tick_interval_seconds=0.01, on_tick=on_tick)
    result = await clock.step()

    assert result == {"tick": 1}
    assert len(calls) == 1


async def test_start_runs_repeatedly_until_paused():
    calls = []

    async def on_tick():
        calls.append(1)
        return {"tick": len(calls)}

    from simllm.sim.clock import SimClock

    clock = SimClock(tick_interval_seconds=0.01, on_tick=on_tick)
    clock.start()
    await asyncio.sleep(0.08)
    clock.pause()
    count_at_pause = len(calls)
    await asyncio.sleep(0.05)

    assert count_at_pause >= 2
    assert len(calls) == count_at_pause
    await clock.shutdown()


async def test_is_paused_reflects_start_and_pause():
    from simllm.sim.clock import SimClock

    async def on_tick():
        return {}

    clock = SimClock(tick_interval_seconds=0.01, on_tick=on_tick)
    assert clock.is_paused is True

    clock.start()
    assert clock.is_paused is False

    clock.pause()
    assert clock.is_paused is True
    await clock.shutdown()


async def test_set_interval_changes_pacing():
    from simllm.sim.clock import SimClock

    clock = SimClock(tick_interval_seconds=5.0, on_tick=lambda: None)
    clock.set_interval(0.5)
    assert clock.tick_interval_seconds == 0.5


async def test_resume_restarts_the_tick_loop_after_pause():
    calls = []

    async def on_tick():
        calls.append(1)
        return {"tick": len(calls)}

    from simllm.sim.clock import SimClock

    clock = SimClock(tick_interval_seconds=0.01, on_tick=on_tick)
    clock.start()
    await asyncio.sleep(0.03)
    clock.pause()
    await asyncio.sleep(0.03)
    count_while_paused = len(calls)

    clock.resume()
    await asyncio.sleep(0.05)
    clock.pause()

    assert len(calls) > count_while_paused
    await clock.shutdown()


async def test_shutdown_cancels_an_in_flight_tick():
    from simllm.sim.clock import SimClock

    started = asyncio.Event()

    async def on_tick():
        started.set()
        await asyncio.sleep(10)  # never completes naturally; shutdown must cancel it
        return {}

    clock = SimClock(tick_interval_seconds=0.01, on_tick=on_tick)
    clock.start()
    await started.wait()

    await clock.shutdown()  # must not hang or raise CancelledError out of shutdown()
    assert clock.is_paused is True
