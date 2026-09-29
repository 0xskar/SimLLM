from __future__ import annotations

from simllm.sim.needs import NEED_FIELDS
from simllm.sim.scheduling import is_agent_due


def healthy_needs() -> dict:
    return {key: 100.0 for key in NEED_FIELDS}


def test_due_on_first_ever_decision():
    # A freshly spawned agent's next_decision_tick defaults to 0, so it's
    # immediately due the first time a tick runs (tick is always >= 1).
    assert is_agent_due(next_decision_tick=0, tick=1, needs=healthy_needs(), critical_threshold=20.0)


def test_not_due_before_cooldown_elapses():
    assert not is_agent_due(next_decision_tick=15, tick=10, needs=healthy_needs(), critical_threshold=20.0)


def test_due_once_cooldown_elapses():
    assert is_agent_due(next_decision_tick=10, tick=10, needs=healthy_needs(), critical_threshold=20.0)
    assert is_agent_due(next_decision_tick=5, tick=10, needs=healthy_needs(), critical_threshold=20.0)


def test_due_on_a_move_s_scheduled_arrival_tick():
    # The engine sets next_decision_tick to the move's arrival tick when a
    # multi-tick path is started; is_agent_due doesn't need a separate
    # "still moving" flag to know when that move finishes.
    assert is_agent_due(next_decision_tick=42, tick=42, needs=healthy_needs(), critical_threshold=20.0)


def test_due_when_any_need_is_critical_even_before_cooldown():
    needs = healthy_needs()
    needs["hunger"] = 5.0

    assert is_agent_due(next_decision_tick=999, tick=10, needs=needs, critical_threshold=20.0)
