from __future__ import annotations

from simllm.sim.needs import critical_needs


def is_agent_due(
    next_decision_tick: int,
    tick: int,
    needs: dict,
    critical_threshold: float,
) -> bool:
    """Decide whether an agent needs a real decision this tick.

    Due once its cooldown has elapsed, or if any need is currently critical
    (distress always interrupts whatever it was doing, cooldown or not).
    `next_decision_tick` alone is enough to cover both a plain cooldown
    *and* a multi-tick move's scheduled arrival tick -- when a move starts,
    the engine sets next_decision_tick to the tick it will finish, so
    arrival makes the agent due again with no separate "still moving" flag
    needed here. This decouples tick rate from LLM-call rate: a content or
    mid-movement agent doesn't consume a worker slot every single tick.
    """
    if next_decision_tick <= tick:
        return True
    if critical_needs(needs, critical_threshold):
        return True
    return False
