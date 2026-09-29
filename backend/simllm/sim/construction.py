"""Construction progress: pure tick-advancement for buildings under
construction. DB-touching orchestration (fetching under-construction
buildings, flipping tile/building status on completion, creating a job for
a finished workplace, linking a finished house to its owner) lives in the
engine.
"""
from __future__ import annotations


def advance_construction(progress: int, total_ticks: int) -> tuple[int, bool]:
    """Returns (new_progress, completed). Progress never exceeds total_ticks."""
    new_progress = min(total_ticks, progress + 1)
    return new_progress, new_progress >= total_ticks
