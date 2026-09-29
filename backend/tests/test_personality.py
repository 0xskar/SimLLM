from __future__ import annotations

from simllm.agents.personality import (
    SEED_HINTS,
    assemble_personality_prompt,
    fallback_identity,
    random_seed_hint,
)


def test_random_seed_hint_returns_one_of_the_known_hints():
    for _ in range(20):
        assert random_seed_hint() in SEED_HINTS


def test_assemble_personality_prompt_includes_seed_hint():
    messages = assemble_personality_prompt("They just arrived in town.")

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "They just arrived in town." in messages[1]["content"]


def test_fallback_identity_is_deterministic_given_same_seed():
    assert fallback_identity(3) == fallback_identity(3)


def test_fallback_identity_varies_across_seeds():
    identities = {fallback_identity(i) for i in range(8)}
    assert len(identities) > 1
