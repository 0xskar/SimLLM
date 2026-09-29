"""Emoji re-pick: a cheap follow-up LLM call triggered only when an agent's
mood crosses into a new band (see sim/mood.py), not every tick. Keeps the
emoji meaningful and agent-chosen without flickering.
"""
from __future__ import annotations

SYSTEM_PROMPT = (
    "Your mood has shifted. Pick a single emoji that best represents how you feel right now."
)

TOOL_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "pick_emoji",
            "description": "Choose the emoji that best represents your current mood.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emoji": {"type": "string", "description": "A single emoji"},
                },
                "required": ["emoji"],
            },
        },
    }
]


def _mood_description(mood: float) -> str:
    if mood > 50:
        return "very positive"
    if mood > 0:
        return "somewhat positive"
    if mood > -50:
        return "somewhat negative"
    return "very negative"


def assemble_emoji_prompt(agent_name: str, mood: float) -> list[dict]:
    user_content = (
        f"You are {agent_name}. Your mood has just shifted to {_mood_description(mood)}.\n"
        "Pick an emoji that captures how you feel right now."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
