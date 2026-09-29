"""Death checks: pure logic for whether an agent's age or sustained zero
health means they've died this tick. DB-touching orchestration (marking
is_alive, releasing their job/house, broadcasting) lives in the engine.
"""
from __future__ import annotations


def check_age_death(age_ticks: int, lifespan_ticks: int) -> bool:
    return age_ticks >= lifespan_ticks


def update_zero_health_streak(health: float, current_streak: int) -> int:
    """Consecutive ticks health has been at (or below) zero. Resets the
    moment health rises above zero again -- a brief dip doesn't kill you,
    only sustained neglect does."""
    if health <= 0.0:
        return current_streak + 1
    return 0


def check_starvation_death(zero_health_streak: int, starvation_death_ticks: int) -> bool:
    return zero_health_streak >= starvation_death_ticks
