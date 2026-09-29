from __future__ import annotations

from simllm.sim.health import apply_health_delta, compute_health_delta
from simllm.sim.needs import NEED_FIELDS


def make_needs(value: float = 100.0) -> dict:
    return {key: value for key in NEED_FIELDS}


def test_health_regenerates_when_no_needs_critical():
    needs = make_needs(50.0)

    delta = compute_health_delta(
        needs, critical_threshold=20.0, regen_per_tick=0.5, decay_per_critical_need=1.0
    )

    assert delta == 0.5


def test_health_decays_scaled_by_critical_need_count():
    needs = make_needs(50.0)
    needs["hunger"] = 5.0
    needs["energy"] = 10.0

    delta = compute_health_delta(
        needs, critical_threshold=20.0, regen_per_tick=0.5, decay_per_critical_need=1.0
    )

    assert delta == -2.0


def test_apply_health_delta_clamps_between_zero_and_hundred():
    assert apply_health_delta(99.7, 0.5) == 100.0
    assert apply_health_delta(0.5, -2.0) == 0.0
    assert apply_health_delta(50.0, -10.0) == 40.0


# Death (age-based and starvation) lands in a later milestone (sim/death.py);
# these tests will grow alongside that module.
