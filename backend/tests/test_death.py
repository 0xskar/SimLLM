from __future__ import annotations

from simllm.sim.death import check_age_death, check_starvation_death, update_zero_health_streak


def test_check_age_death_true_when_age_meets_lifespan():
    assert check_age_death(100, 100)
    assert check_age_death(101, 100)


def test_check_age_death_false_before_lifespan():
    assert not check_age_death(99, 100)


def test_update_zero_health_streak_increments_at_zero():
    assert update_zero_health_streak(0.0, 5) == 6


def test_update_zero_health_streak_increments_below_zero():
    assert update_zero_health_streak(-1.0, 5) == 6


def test_update_zero_health_streak_resets_when_health_recovers():
    assert update_zero_health_streak(0.1, 50) == 0


def test_check_starvation_death_true_once_streak_meets_threshold():
    assert check_starvation_death(288, 288)
    assert check_starvation_death(300, 288)


def test_check_starvation_death_false_before_threshold():
    assert not check_starvation_death(287, 288)
