from __future__ import annotations

from simllm.sim.needs import critical_needs


def compute_health_delta(
    needs: dict,
    critical_threshold: float,
    regen_per_tick: float,
    decay_per_critical_need: float,
) -> float:
    """Health drains while needs stay critical, regenerates otherwise.

    Because this is recomputed fresh every tick from the current needs
    (not from a separate "ticks spent critical" counter), health only
    trends downward while a deficit is *sustained* tick over tick -- a
    single bad tick barely dents it, but neglecting a need for a long
    stretch compounds. This is what later milestones (starvation death)
    build on.
    """
    critical = critical_needs(needs, critical_threshold)
    if not critical:
        return regen_per_tick
    return -decay_per_critical_need * len(critical)


def apply_health_delta(health: float, delta: float) -> float:
    return max(0.0, min(100.0, health + delta))
