from __future__ import annotations

from simllm.sim.mood import compute_mood, compute_mood_band
from simllm.sim.needs import NEED_FIELDS


def make_needs(value: float) -> dict:
    return {key: value for key in NEED_FIELDS}


def test_compute_mood_is_zero_at_midpoint_wellbeing():
    assert compute_mood(make_needs(50.0), health=50.0) == 0.0


def test_compute_mood_is_maximally_positive_when_everything_is_full():
    assert compute_mood(make_needs(100.0), health=100.0) == 100.0


def test_compute_mood_is_maximally_negative_when_everything_is_zero():
    assert compute_mood(make_needs(0.0), health=0.0) == -100.0


def test_compute_mood_averages_needs_and_health_equally():
    # needs avg 100, health 0 -> overall wellbeing avg 50 -> mood 0
    assert compute_mood(make_needs(100.0), health=0.0) == 0.0


def test_compute_mood_band_buckets_by_width():
    assert compute_mood_band(0.0, 25) == 0
    assert compute_mood_band(24.9, 25) == 0
    assert compute_mood_band(25.0, 25) == 1
    assert compute_mood_band(-0.1, 25) == -1
    assert compute_mood_band(99.0, 25) == 3
    assert compute_mood_band(-100.0, 25) == -4
