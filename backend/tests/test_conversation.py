from __future__ import annotations

from simllm.agents.conversation import assemble_relationship_prompt, assemble_reply_prompt


def test_reply_prompt_includes_transcript_and_names():
    agent = {"name": "Bailey"}
    transcript = ["Alex: Hi there!"]

    messages = assemble_reply_prompt(agent, "Alex", transcript)

    content = messages[1]["content"]
    assert "Bailey" in content
    assert "Alex" in content
    assert "Hi there!" in content


def test_relationship_prompt_includes_previous_note_when_present():
    agent = {"name": "Alex"}
    transcript = ["Alex: Hi!", "Bailey: Hello!"]

    messages = assemble_relationship_prompt(agent, "Bailey", transcript, previous_note="We're old friends.")

    content = messages[1]["content"]
    assert "We're old friends." in content
    assert "Hi!" in content


def test_relationship_prompt_handles_no_previous_note():
    messages = assemble_relationship_prompt({"name": "Alex"}, "Bailey", ["Alex: Hi!"], previous_note=None)

    assert "no prior relationship" in messages[1]["content"]
