"""Turn-based conversation resolution between two agents, entirely within
one tick. The opening line comes from the initiator's own `speak` decision
(see agents/actions.py); this module assembles the reply-turn and
relationship-update prompts. See SimulationEngine._resolve_conversation for
why only two agents who are BOTH due in the same tick can end up talking --
a target that already resolved its own decision this tick is "busy" from
the initiator's perspective, not retroactively pulled into a conversation.
"""
from __future__ import annotations

REPLY_SYSTEM_PROMPT = (
    "You are having a spoken conversation with another resident of your city. "
    "Reply naturally and briefly (one or two sentences), in character, given the "
    "conversation so far. Respond with your spoken reply only -- no narration, no quotes."
)

RELATIONSHIP_SYSTEM_PROMPT = (
    "You just finished a conversation with another resident. Call update_relationship "
    "to record how it affected your feelings about them."
)

RELATIONSHIP_UPDATE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "update_relationship",
            "description": "Record how this conversation affected your feelings about the other person.",
            "parameters": {
                "type": "object",
                "properties": {
                    "affinity_delta": {
                        "type": "integer",
                        "description": "-20 to 20: how much your feelings toward them changed because of this conversation.",
                    },
                    "note": {
                        "type": "string",
                        "description": "A short first-person note about your relationship with them, replacing any previous note.",
                    },
                },
                "required": ["affinity_delta", "note"],
            },
        },
    }
]


def assemble_reply_prompt(agent: dict, other_name: str, transcript: list[str]) -> list[dict]:
    lines = "\n".join(transcript)
    user_content = (
        f"You are {agent['name']}, talking with {other_name}.\n\n"
        f"Conversation so far:\n{lines}\n\n"
        "What do you say next?"
    )
    return [
        {"role": "system", "content": REPLY_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def assemble_relationship_prompt(
    agent: dict, other_name: str, transcript: list[str], previous_note: str | None
) -> list[dict]:
    lines = "\n".join(transcript)
    note_text = previous_note or "(no prior relationship)"
    user_content = (
        f"You are {agent['name']}. You just talked with {other_name}.\n\n"
        f"Conversation:\n{lines}\n\n"
        f"Your previous note about {other_name}: {note_text}\n\n"
        "Call update_relationship now."
    )
    return [
        {"role": "system", "content": RELATIONSHIP_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
