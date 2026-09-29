from __future__ import annotations

from simllm.sim.construction import advance_construction


def test_advance_construction_increments_progress():
    progress, completed = advance_construction(5, 10)

    assert progress == 6
    assert not completed


def test_advance_construction_completes_when_reaching_total():
    progress, completed = advance_construction(9, 10)

    assert progress == 10
    assert completed


def test_advance_construction_never_exceeds_total():
    progress, completed = advance_construction(10, 10)

    assert progress == 10
    assert completed


def test_advance_construction_completes_immediately_for_zero_total():
    progress, completed = advance_construction(0, 0)

    assert progress == 0
    assert completed
