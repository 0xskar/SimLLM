from __future__ import annotations

NEED_FIELDS = ["hunger", "energy", "social", "shelter", "hygiene", "fun", "purpose"]


def decay_needs(needs: dict, decay_rates: dict) -> dict:
    """Apply one tick of decay to every need, clamped at 0."""
    return {key: max(0.0, needs[key] - decay_rates[key]) for key in NEED_FIELDS}


def restore_need(needs: dict, key: str, amount: float) -> dict:
    """Return needs with `key` increased by `amount`, clamped at 100."""
    updated = dict(needs)
    updated[key] = min(100.0, needs[key] + amount)
    return updated


def critical_needs(needs: dict, threshold: float) -> list[str]:
    return [key for key in NEED_FIELDS if needs[key] < threshold]
