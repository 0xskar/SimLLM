"""Prompt assembly for an agent's decision turn.

Milestone 10 scope: personality + needs/stats + life summary + recent
memory buffer + local perception (nearby buildings/agents/job openings,
radius-filtered by sim/perception.py) + the agent's current job, if any.
Relationship context is added by a later pass as an extra section appended
before the closing instruction -- this function's signature and contract
(pure, given already-fetched snapshots) won't need to change.
"""
from __future__ import annotations

from simllm.models.settings import Settings

SYSTEM_PROMPT = (
    "You are a resident of a small simulated city, living your life turn by turn. "
    "Respond only by calling exactly one of the provided tools to choose your action "
    "this turn. Always include a brief `reason` describing your thinking."
)


def assemble_prompt(
    agent: dict,
    settings: Settings,
    memories: list[dict] | None = None,
    perception: dict | None = None,
) -> list[dict]:
    needs_lines = [
        f"- {key}: {value:.0f}" + (" (critical!)" if value < settings.needs_critical_threshold else "")
        for key, value in agent["needs"].items()
    ]

    summary_section = ""
    if agent.get("life_summary"):
        summary_section = f"\nYour life so far: {agent['life_summary']}\n"

    memory_section = ""
    if memories:
        memory_lines = [f"- (tick {m['tick']}) {m['content']}" for m in memories]
        memory_section = "\nThings that recently happened to you:\n" + "\n".join(memory_lines) + "\n"

    job_section = ""
    if agent.get("current_job"):
        job = agent["current_job"]
        job_section = (
            f"\nYou have a job: {job['title']} at ({job['x']}, {job['y']}), "
            f"paying {job['wage_per_shift']:.0f} per shift worked.\n"
        )

    perception_section = ""
    if perception:
        lines = [f"- {b['type']} at ({b['x']}, {b['y']})" for b in perception.get("buildings", [])]
        lines += [
            f"- {a['name']} (id {a['id']}) at ({a['x']}, {a['y']})"
            + (f", {a['current_goal']}" if a.get("current_goal") else "")
            for a in perception.get("agents", [])
        ]
        lines += [
            f"- Job opening: {j['title']} (id {j['id']}) at ({j['x']}, {j['y']}), "
            f"pays {j['wage_per_shift']:.0f}/shift, {j['slots'] - j['filled']} slot(s) open"
            for j in perception.get("jobs", [])
            if j["filled"] < j["slots"]
        ]
        if lines:
            perception_section = "\nWhat's nearby:\n" + "\n".join(lines) + "\n"

    user_content = (
        f"You are {agent['name']} {agent['emoji']}, age {agent['age_ticks']} ticks.\n"
        f"Position: ({agent['x']}, {agent['y']}) in a "
        f"{settings.world_width}x{settings.world_height} city.\n"
        f"Health: {agent['health']:.0f}/100. Currency: {agent['currency']:.0f}.\n"
        + summary_section
        + memory_section
        + job_section
        + perception_section
        + "\nYour current needs:\n" + "\n".join(needs_lines) + "\n\n"
        "Choose exactly one action now."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
