"""Agent action schema: Ollama tool-calling specs plus server-side
validation/application.

`speak`, `take_job`, `work_job`, and `start_build` here only do structural
validation (a real message/plausible id, an in-bounds target) and hand back
a `pending_action` -- like `move_to`, resolving them for real (is the
target alive and in range? is the job open and is the agent at the
workplace? is the build site actually empty and adjacent, and can the
agent afford it?) needs state this pure module doesn't have, so that's the
engine's job (see SimulationEngine._resolve_conversation and the
take_job/work_job/start_build handling in _apply_decision).
"""
from __future__ import annotations

from dataclasses import dataclass

from simllm.models.settings import Settings


@dataclass(frozen=True)
class AgentContext:
    x: int
    y: int
    needs: dict
    currency: float
    home_pos: tuple[int, int] | None
    world_width: int
    world_height: int


@dataclass(frozen=True)
class ActionOutcome:
    accepted: bool
    x: int
    y: int
    needs: dict
    currency: float
    goal_text: str
    reason: str | None = None  # rejection reason code, for logging
    # Set only by move_to: {"type": "move_to", "target": [x, y]}. The engine
    # (which has DB access for pathfinding) turns this into an actual
    # multi-tick path; actions.py stays pure and never touches x/y for a
    # move_to itself -- position only changes as the path is walked.
    pending_action: dict | None = None


def _in_bounds(x: object, y: object, width: int, height: int) -> bool:
    return isinstance(x, int) and isinstance(y, int) and 0 <= x < width and 0 <= y < height


def _restore(ctx: AgentContext, key: str, amount: float) -> dict:
    updated = dict(ctx.needs)
    updated[key] = min(100.0, ctx.needs[key] + amount)
    return updated


def _apply_move_to(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    x = params.get("target_x")
    y = params.get("target_y")
    if not _in_bounds(x, y, ctx.world_width, ctx.world_height):
        return ActionOutcome(
            False, ctx.x, ctx.y, ctx.needs, ctx.currency,
            "Tried to move somewhere invalid.", "out_of_bounds",
        )
    return ActionOutcome(
        True, ctx.x, ctx.y, ctx.needs, ctx.currency, reason_text or "Setting off.",
        pending_action={"type": "move_to", "target": [x, y]},
    )


def _apply_eat(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    if ctx.currency < settings.food_cost:
        return ActionOutcome(
            False, ctx.x, ctx.y, ctx.needs, ctx.currency,
            "Wanted to eat but couldn't afford it.", "insufficient_funds",
        )
    needs = _restore(ctx, "hunger", settings.needs_restore_amount.hunger)
    currency = ctx.currency - settings.food_cost
    return ActionOutcome(True, ctx.x, ctx.y, needs, currency, reason_text or "Eating.")


def _apply_sleep(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    needs = _restore(ctx, "energy", settings.needs_restore_amount.energy)
    return ActionOutcome(True, ctx.x, ctx.y, needs, ctx.currency, reason_text or "Sleeping.")


def _apply_wash_up(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    needs = _restore(ctx, "hygiene", settings.needs_restore_amount.hygiene)
    return ActionOutcome(True, ctx.x, ctx.y, needs, ctx.currency, reason_text or "Washing up.")


def _apply_have_fun(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    needs = _restore(ctx, "fun", settings.needs_restore_amount.fun)
    return ActionOutcome(True, ctx.x, ctx.y, needs, ctx.currency, reason_text or "Having fun.")


def _apply_idle(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    return ActionOutcome(True, ctx.x, ctx.y, ctx.needs, ctx.currency, reason_text or "Idling.")


def _apply_speak(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    target_agent_id = params.get("target_agent_id")
    message = params.get("message")
    if not isinstance(target_agent_id, int) or not isinstance(message, str) or not message.strip():
        return ActionOutcome(
            False, ctx.x, ctx.y, ctx.needs, ctx.currency,
            "Tried to say something but wasn't clear who to.", "invalid_speak_params",
        )
    return ActionOutcome(
        True, ctx.x, ctx.y, ctx.needs, ctx.currency, reason_text or "Starting a conversation.",
        pending_action={"type": "speak", "target_agent_id": target_agent_id, "message": message.strip()},
    )


def _apply_take_job(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    job_id = params.get("job_id")
    if not isinstance(job_id, int):
        return ActionOutcome(
            False, ctx.x, ctx.y, ctx.needs, ctx.currency,
            "Tried to take a job but wasn't clear which one.", "invalid_job_id",
        )
    return ActionOutcome(
        True, ctx.x, ctx.y, ctx.needs, ctx.currency, reason_text or "Applying for a job.",
        pending_action={"type": "take_job", "job_id": job_id},
    )


def _apply_work_job(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    return ActionOutcome(
        True, ctx.x, ctx.y, ctx.needs, ctx.currency, reason_text or "Working a shift.",
        pending_action={"type": "work_job"},
    )


def _apply_start_build(ctx: AgentContext, params: dict, settings: Settings, reason_text: str) -> ActionOutcome:
    building_type = params.get("building_type")
    x = params.get("target_x")
    y = params.get("target_y")
    if building_type not in ("house", "workplace") or not _in_bounds(x, y, ctx.world_width, ctx.world_height):
        return ActionOutcome(
            False, ctx.x, ctx.y, ctx.needs, ctx.currency,
            "Tried to build something invalid.", "invalid_build_params",
        )
    return ActionOutcome(
        True, ctx.x, ctx.y, ctx.needs, ctx.currency, reason_text or "Starting construction.",
        pending_action={"type": "start_build", "building_type": building_type, "target": [x, y]},
    )


ACTION_HANDLERS = {
    "move_to": _apply_move_to,
    "eat": _apply_eat,
    "sleep": _apply_sleep,
    "wash_up": _apply_wash_up,
    "have_fun": _apply_have_fun,
    "idle": _apply_idle,
    "speak": _apply_speak,
    "take_job": _apply_take_job,
    "work_job": _apply_work_job,
    "start_build": _apply_start_build,
}

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "move_to",
            "description": "Walk to a specific tile in the city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_x": {"type": "integer"},
                    "target_y": {"type": "integer"},
                    "reason": {"type": "string", "description": "Brief inner-monologue reason"},
                },
                "required": ["target_x", "target_y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "eat",
            "description": "Buy and eat food to restore your hunger. Costs currency.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep",
            "description": "Rest to restore your energy.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wash_up",
            "description": "Wash up to restore your hygiene.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "have_fun",
            "description": "Do something enjoyable to restore your fun need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity": {"type": "string", "description": "What you do for fun"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "idle",
            "description": "Do nothing this turn. Use when nothing urgent needs attention.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": "Start a conversation with another agent who is nearby.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_agent_id": {"type": "integer", "description": "The id of the agent to talk to"},
                    "message": {"type": "string", "description": "What you want to say to them"},
                    "reason": {"type": "string"},
                },
                "required": ["target_agent_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_job",
            "description": "Apply for and accept an open job slot at a workplace you are at or near.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "integer", "description": "The id of the job to take"},
                    "reason": {"type": "string"},
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "work_job",
            "description": (
                "Work a shift at your assigned job. You must be at the workplace. "
                "Restores purpose, costs energy, and pays your wage."
            ),
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_build",
            "description": (
                "Claim an empty tile you are at or next to and begin constructing a building there. "
                "Costs currency immediately; the building completes automatically after some time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "building_type": {"type": "string", "enum": ["house", "workplace"]},
                    "target_x": {"type": "integer"},
                    "target_y": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["building_type", "target_x", "target_y"],
            },
        },
    },
]


def apply_action(action_name: str, params: dict, ctx: AgentContext, settings: Settings) -> ActionOutcome:
    """Validate and apply one action. Never raises; unknown/illegal actions
    come back as a rejected outcome (unchanged state) for the caller to
    fall back to idle."""
    handler = ACTION_HANDLERS.get(action_name)
    params = params or {}
    reason_text = params.get("reason") if isinstance(params.get("reason"), str) else ""

    if handler is None:
        return ActionOutcome(
            False, ctx.x, ctx.y, ctx.needs, ctx.currency,
            "Tried an unavailable action.", "unknown_action",
        )
    return handler(ctx, params, settings, reason_text)
