"""Ollama wrapper: timeout + one retry, then a safe fallback.

Never raises -- a timeout, connection error, or an empty/missing response
all resolve to a fallback (mirrors how an invalid server-side action
outcome is handled), so a single bad LLM call can never stall or crash a
tick. Every attempt's outcome is captured in the returned result for the
caller to log.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import ollama

from simllm.agents.actions import TOOL_SPECS
from simllm.models.settings import Settings


class ChatClient(Protocol):
    async def chat(self, *, model: str, messages: list[dict], tools: list[dict]) -> Any: ...


@dataclass
class LLMDecision:
    action: str
    params: dict
    latency_ms: float
    used_fallback: bool
    attempts: int
    error: str | None = None


def _make_client(settings: Settings) -> ChatClient:
    return ollama.AsyncClient(host=settings.ollama_host)


async def decide_action(
    messages: list[dict],
    settings: Settings,
    client: ChatClient | None = None,
    tools: list[dict] | None = None,
) -> LLMDecision:
    """Tool-calling call. Defaults to the main agent action schema
    (TOOL_SPECS), but accepts an override -- e.g. the single-tool
    `update_relationship` schema used after a conversation -- since the
    retry/fallback/parsing logic is identical either way."""
    chat_client = client if client is not None else _make_client(settings)
    tool_specs = tools if tools is not None else TOOL_SPECS

    last_error: str | None = None
    attempts = 0

    for _ in range(settings.llm_max_retries + 1):
        attempts += 1
        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                chat_client.chat(model=settings.ollama_model, messages=messages, tools=tool_specs),
                timeout=settings.llm_timeout_seconds,
            )
        except asyncio.TimeoutError:
            last_error = "timeout"
            continue
        except Exception as exc:  # connection errors, malformed server responses, etc.
            last_error = f"error: {exc}"
            continue

        latency_ms = (time.monotonic() - start) * 1000
        tool_calls = getattr(response.message, "tool_calls", None) or []
        if not tool_calls:
            last_error = "no_tool_call"
            continue

        call = tool_calls[0]
        name = call.function.name
        arguments = call.function.arguments
        params = arguments if isinstance(arguments, dict) else {}

        return LLMDecision(
            action=name, params=params, latency_ms=latency_ms, used_fallback=False, attempts=attempts
        )

    return LLMDecision(
        action="idle",
        params={"reason": "Couldn't decide -- lost in thought."},
        latency_ms=0.0,
        used_fallback=True,
        attempts=attempts,
        error=last_error,
    )


@dataclass
class SummaryResult:
    text: str | None
    latency_ms: float
    used_fallback: bool
    attempts: int
    error: str | None = None


async def generate_text(
    messages: list[dict],
    settings: Settings,
    client: ChatClient | None = None,
    max_chars: int | None = None,
) -> SummaryResult:
    """Plain-text (no tool-calling) LLM call, same timeout/retry/
    never-raises contract as decide_action. Used for both the periodic
    life-summary update and conversation reply turns -- on failure,
    `text` is None and the caller just skips this round."""
    chat_client = client if client is not None else _make_client(settings)

    last_error: str | None = None
    attempts = 0

    for _ in range(settings.llm_max_retries + 1):
        attempts += 1
        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                chat_client.chat(model=settings.ollama_model, messages=messages, tools=[]),
                timeout=settings.llm_timeout_seconds,
            )
        except asyncio.TimeoutError:
            last_error = "timeout"
            continue
        except Exception as exc:
            last_error = f"error: {exc}"
            continue

        latency_ms = (time.monotonic() - start) * 1000
        content = getattr(response.message, "content", None)
        if not content or not content.strip():
            last_error = "empty_response"
            continue

        text = content.strip()
        if max_chars is not None:
            text = text[:max_chars]
        return SummaryResult(text=text, latency_ms=latency_ms, used_fallback=False, attempts=attempts)

    return SummaryResult(text=None, latency_ms=0.0, used_fallback=True, attempts=attempts, error=last_error)


async def summarize(
    messages: list[dict],
    settings: Settings,
    client: ChatClient | None = None,
) -> SummaryResult:
    return await generate_text(messages, settings, client=client, max_chars=settings.life_summary_max_chars)
