from __future__ import annotations

from simllm.sim.needs import NEED_FIELDS, critical_needs, decay_needs, restore_need


def make_needs(value: float = 100.0) -> dict:
    return {key: value for key in NEED_FIELDS}


def test_decay_needs_subtracts_rate_per_field():
    needs = make_needs(50.0)
    rates = {key: 1.0 for key in NEED_FIELDS}
    rates["hunger"] = 2.5

    result = decay_needs(needs, rates)

    assert result["hunger"] == 47.5
    assert result["energy"] == 49.0


def test_decay_needs_clamps_at_zero():
    needs = make_needs(0.5)
    rates = {key: 5.0 for key in NEED_FIELDS}

    result = decay_needs(needs, rates)

    assert all(v == 0.0 for v in result.values())


def test_restore_need_clamps_at_one_hundred():
    needs = make_needs(95.0)

    result = restore_need(needs, "hunger", 20.0)

    assert result["hunger"] == 100.0
    assert result["energy"] == 95.0  # untouched


def test_restore_need_does_not_mutate_input():
    needs = make_needs(50.0)
    restore_need(needs, "hunger", 10.0)

    assert needs["hunger"] == 50.0


def test_critical_needs_returns_only_fields_below_threshold():
    needs = make_needs(50.0)
    needs["hunger"] = 10.0
    needs["fun"] = 19.9

    result = critical_needs(needs, threshold=20.0)

    assert set(result) == {"hunger", "fun"}
