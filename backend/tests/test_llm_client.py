from __future__ import annotations

import asyncio
from types import SimpleNamespace

from simllm.agents.llm_client import decide_action, summarize
from simllm.config import default_settings


def make_response(name: str, arguments: dict):
    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))
    message = SimpleNamespace(tool_calls=[call])
    return SimpleNamespace(message=message)


def make_text_response(content: str):
    return SimpleNamespace(message=SimpleNamespace(content=content))


class ScriptedClient:
    """Fake ChatClient that plays back a scripted sequence of outcomes,
    so the retry/fallback wrapper can be tested with no real LLM server."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def chat(self, *, model, messages, tools):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def test_successful_first_attempt_returns_decision():
    client = ScriptedClient([make_response("eat", {"reason": "hungry"})])
    settings = default_settings()

    decision = await decide_action([{"role": "user", "content": "hi"}], settings, client=client)

    assert decision.action == "eat"
    assert decision.params == {"reason": "hungry"}
    assert not decision.used_fallback
    assert decision.attempts == 1
    assert client.calls == 1


async def test_timeout_then_success_uses_retry():
    client = ScriptedClient([asyncio.TimeoutError(), make_response("sleep", {})])
    settings = default_settings().model_copy(update={"llm_max_retries": 1})

    decision = await decide_action([], settings, client=client)

    assert decision.action == "sleep"
    assert decision.attempts == 2
    assert not decision.used_fallback


async def test_exhausted_retries_falls_back_to_idle():
    client = ScriptedClient([asyncio.TimeoutError(), asyncio.TimeoutError()])
    settings = default_settings().model_copy(update={"llm_max_retries": 1})

    decision = await decide_action([], settings, client=client)

    assert decision.action == "idle"
    assert decision.used_fallback
    assert decision.error == "timeout"


async def test_response_with_no_tool_call_falls_back_to_idle():
    empty_response = SimpleNamespace(message=SimpleNamespace(tool_calls=[]))
    client = ScriptedClient([empty_response])
    settings = default_settings().model_copy(update={"llm_max_retries": 0})

    decision = await decide_action([], settings, client=client)

    assert decision.action == "idle"
    assert decision.used_fallback
    assert decision.error == "no_tool_call"


async def test_connection_error_falls_back_to_idle():
    client = ScriptedClient([ConnectionRefusedError("no server")])
    settings = default_settings().model_copy(update={"llm_max_retries": 0})

    decision = await decide_action([], settings, client=client)

    assert decision.action == "idle"
    assert decision.used_fallback
    assert "no server" in decision.error


async def test_summarize_returns_trimmed_text_on_success():
    client = ScriptedClient([make_text_response("  Alex enjoys quiet mornings.  ")])
    settings = default_settings()

    result = await summarize([{"role": "user", "content": "hi"}], settings, client=client)

    assert result.text == "Alex enjoys quiet mornings."
    assert not result.used_fallback


async def test_summarize_truncates_to_max_chars():
    settings = default_settings().model_copy(update={"life_summary_max_chars": 5})
    client = ScriptedClient([make_text_response("way too long a summary")])

    result = await summarize([], settings, client=client)

    assert result.text == "way t"


async def test_summarize_empty_response_falls_back():
    settings = default_settings().model_copy(update={"llm_max_retries": 0})
    client = ScriptedClient([make_text_response("")])

    result = await summarize([], settings, client=client)

    assert result.text is None
    assert result.used_fallback
    assert result.error == "empty_response"


async def test_summarize_timeout_falls_back():
    settings = default_settings().model_copy(update={"llm_max_retries": 0})
    client = ScriptedClient([asyncio.TimeoutError()])

    result = await summarize([], settings, client=client)

    assert result.text is None
    assert result.used_fallback
    assert result.error == "timeout"
