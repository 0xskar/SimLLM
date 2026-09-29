"""Mood: a derived wellbeing score from needs + health, cheap to recompute
every tick. Emoji only gets re-picked when mood crosses into a new BAND
(see agents/emoji.py and SimulationEngine._run_emoji_repicks) -- not every
tick, so the emoji doesn't flicker on tiny fluctuations.
"""
from __future__ import annotations

import math

from simllm.sim.needs import NEED_FIELDS


def compute_mood(needs: dict, health: float) -> float:
    """-100..100, from the average of all needs and health (both already
    0..100): "everything terrible" maps to -100, "everything great" to +100."""
    avg_need = sum(needs[key] for key in NEED_FIELDS) / len(NEED_FIELDS)
    avg_wellbeing = (avg_need + health) / 2.0
    return (avg_wellbeing - 50.0) * 2.0


def compute_mood_band(mood: float, band_width: float) -> int:
    return math.floor(mood / band_width)
