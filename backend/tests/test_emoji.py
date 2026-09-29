from __future__ import annotations

from simllm.agents.emoji import assemble_emoji_prompt


def test_assemble_emoji_prompt_includes_name():
    messages = assemble_emoji_prompt("Alex", mood=10.0)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Alex" in messages[1]["content"]


def test_assemble_emoji_prompt_describes_positive_mood():
    content = assemble_emoji_prompt("Alex", mood=80.0)[1]["content"]
    assert "very positive" in content


def test_assemble_emoji_prompt_describes_negative_mood():
    content = assemble_emoji_prompt("Alex", mood=-80.0)[1]["content"]
    assert "very negative" in content
