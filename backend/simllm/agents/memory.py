"""Agent memory policy: when to compress the recent-events buffer into an
updated running life summary (the "generative agents" pattern), and how to
prompt the LLM to do it. All raw events live forever in the `memories`
table for the inspector's history view; only the most recent
`memory_buffer_size` are ever included verbatim in a decision prompt --
everything older is represented only through `life_summary`.
"""
from __future__ import annotations

from simllm.models.settings import Settings

SUMMARY_SYSTEM_PROMPT = (
    "You maintain a short running life summary for a resident of a simulated city. "
    "Given their previous summary (if any) and their recent memories, write an updated, "
    "concise summary of who they are and what has happened in their life so far. "
    "Focus on lasting facts, relationships, and notable events, not routine daily needs. "
    "Respond with the summary text only, no preamble or labels."
)


def should_summarize(
    tick: int, life_summary_updated_tick: int | None, created_at_tick: int, interval_ticks: int
) -> bool:
    baseline = life_summary_updated_tick if life_summary_updated_tick is not None else created_at_tick
    return (tick - baseline) >= interval_ticks


def assemble_summary_prompt(agent: dict, memories: list[dict], settings: Settings) -> list[dict]:
    previous = agent.get("life_summary") or "(no previous summary yet -- this is their first)"
    memory_lines = [f"- (tick {m['tick']}) {m['content']}" for m in memories]
    memories_text = "\n".join(memory_lines) if memory_lines else "(nothing notable)"

    user_content = (
        f"{agent['name']}'s previous summary:\n{previous}\n\n"
        f"Recent memories since then:\n{memories_text}\n\n"
        f"Write an updated summary in at most {settings.life_summary_max_chars} characters."
    )

    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
