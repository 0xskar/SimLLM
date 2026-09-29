"""LLM-generated agent identity: name, backstory, traits, and an emoji,
from a single structured call. Used whenever a newcomer is spawned to
replace someone who died (see SimulationEngine._maybe_spawn_newcomer).

The very first population (spawned at save creation) still uses simple
placeholder identities (see save_repo.STARTER_NAMES) to keep save creation
fast and deterministic for tests -- this module is only exercised at
runtime, through the same bounded pacing as everything else the engine
calls the LLM for.
"""
from __future__ import annotations

import random

SYSTEM_PROMPT = (
    "You are creating a new resident for a small simulated city. Invent a plausible, "
    "distinct person: a first name, a one-sentence backstory, three short personality "
    "traits, and a single emoji that represents them. Call create_personality now."
)

SEED_HINTS = [
    "They recently moved to town looking for a fresh start.",
    "They grew up here and know the city well.",
    "They are a curious traveler who decided to settle down.",
    "They are looking for work and a place to call home.",
    "They just finished their studies and are starting adult life.",
]

TOOL_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "create_personality",
            "description": "Define a new resident's identity and personality.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "backstory": {"type": "string"},
                    "traits": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Three short personality traits",
                    },
                    "emoji": {"type": "string", "description": "A single emoji representing them"},
                },
                "required": ["name", "backstory", "traits", "emoji"],
            },
        },
    }
]

FALLBACK_NAMES = ["Taylor", "Morgan", "Jordan", "Riley", "Avery", "Quinn", "Sage", "Rowan"]
FALLBACK_EMOJIS = ["🙂", "😊", "🙃", "😀", "🧑", "🙋", "🌟", "🍀"]


def random_seed_hint() -> str:
    return random.choice(SEED_HINTS)


def assemble_personality_prompt(seed_hint: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Create a new resident. {seed_hint}"},
    ]


def fallback_identity(seed: int) -> tuple[str, str]:
    """Deterministic-ish placeholder identity if the LLM call fails --
    respawn must never be blocked on a flaky model."""
    return FALLBACK_NAMES[seed % len(FALLBACK_NAMES)], FALLBACK_EMOJIS[seed % len(FALLBACK_EMOJIS)]
