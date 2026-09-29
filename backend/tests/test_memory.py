from __future__ import annotations

from simllm.agents.memory import assemble_summary_prompt, should_summarize
from simllm.config import default_settings


def test_not_due_before_first_interval_elapses():
    assert not should_summarize(
        tick=100, life_summary_updated_tick=None, created_at_tick=0, interval_ticks=144
    )


def test_due_once_first_interval_elapses_from_creation():
    assert should_summarize(
        tick=144, life_summary_updated_tick=None, created_at_tick=0, interval_ticks=144
    )


def test_due_measured_from_last_summary_not_creation():
    assert not should_summarize(
        tick=200, life_summary_updated_tick=150, created_at_tick=0, interval_ticks=144
    )
    assert should_summarize(
        tick=294, life_summary_updated_tick=150, created_at_tick=0, interval_ticks=144
    )


def test_summary_prompt_includes_previous_summary_and_memories():
    agent = {"name": "Alex", "life_summary": "Alex is a cheerful baker."}
    memories = [{"tick": 10, "content": "Ate breakfast."}, {"tick": 11, "content": "Went for a walk."}]

    messages = assemble_summary_prompt(agent, memories, default_settings())

    content = messages[1]["content"]
    assert "Alex is a cheerful baker." in content
    assert "Ate breakfast." in content
    assert "Went for a walk." in content


def test_summary_prompt_handles_no_previous_summary_and_no_memories():
    agent = {"name": "Alex", "life_summary": None}

    messages = assemble_summary_prompt(agent, [], default_settings())

    content = messages[1]["content"]
    assert "no previous summary" in content
    assert "nothing notable" in content
