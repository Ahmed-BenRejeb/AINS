"""Cloudflare Workers AI client for the atlassian-remote backend.

Every LLM and embedding call goes through here — never the Anthropic or OpenAI
SDKs (root ``CLAUDE.md`` Section 7). Two entry points, matching the eval-engine
client:

* :func:`cf_ai_chat`  — chat completion (RCA drafting, Llama 3.3 70B).
* :func:`cf_ai_embed` — BGE embeddings, 768-dim (xqdrant query vectors).

Tests monkeypatch these functions (``monkeypatch`` the module attribute), so no
real network call is made.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
from collections.abc import Iterator
from typing import Any

import httpx

from .config import (
    CF_TIMEOUT_SECONDS,
    DEFAULT_MAX_TOKENS,
    cf_ai_url,
    cf_api_token,
    model_embed,
    model_main,
)

# Task-local recording transport. When set (by the analyzer's RunRecorder), every
# CF Workers AI call this client makes is routed through the flight recorder's
# AsyncRecordingTransport and taped into the run's cassette. ``None`` → httpx uses
# its default transport (live, unrecorded), so /search and /embed are unaffected.
_active_transport: contextvars.ContextVar[httpx.AsyncBaseTransport | None] = contextvars.ContextVar(
    "cf_ai_active_transport", default=None
)


@contextlib.contextmanager
def using_transport(transport: httpx.AsyncBaseTransport | None) -> Iterator[None]:
    """Route this client's CF Workers AI calls through ``transport`` for the block.

    Used by the analyzer to capture RCA-generation LLM calls into a cassette. The
    contextvar is reset on exit, so the binding is scoped to the ``with`` block and
    safe under concurrency.

    Args:
        transport: The flight recorder's recording transport, or ``None`` to clear.
    """
    token = _active_transport.set(transport)
    try:
        yield
    finally:
        _active_transport.reset(token)


async def _post(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST a payload to a Workers AI model and return its ``result`` object.

    Args:
        model: The CF model id (e.g. ``@cf/meta/llama-3.3-70b-instruct-fp8-fast``).
        payload: The JSON request body.

    Returns:
        The ``result`` object from the Workers AI response envelope.
    """
    async with httpx.AsyncClient(
        timeout=CF_TIMEOUT_SECONDS, transport=_active_transport.get()
    ) as client:
        response = await client.post(
            f"{cf_ai_url()}/{model}",
            headers={"Authorization": f"Bearer {cf_api_token()}"},
            json=payload,
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    result: dict[str, Any] = body.get("result", {})
    return result


async def cf_ai_chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Call a Workers AI chat-completion model and return the text response.

    Args:
        messages: OpenAI-style ``role``/``content`` messages.
        model: Model id; defaults to ``CF_AI_MODEL_MAIN`` (Llama 3.3 70B).
        max_tokens: Completion token budget.

    Returns:
        The assistant's response text.
    """
    result = await _post(
        model or model_main(),
        {"messages": messages, "max_tokens": max_tokens},
    )
    return _response_text(result)


def _response_text(result: dict[str, Any]) -> str:
    """Extract the chat response as text, normalizing CF's JSON-mode output.

    Cloudflare Workers AI auto-parses JSON the model emits, so ``result.response``
    comes back as a ``dict``/``list`` (not a ``str``) whenever the model outputs
    valid JSON — which the RCA prompt always asks it to do. Re-serialize those so
    the ``-> str`` contract holds and ``rca_generator`` can validate the JSON.

    Args:
        result: The ``result`` object from a Workers AI chat response.

    Returns:
        The assistant's response as a string (JSON text when CF parsed it).
    """
    response = result.get("response", "")
    if isinstance(response, str):
        return response
    return json.dumps(response)


async def cf_ai_embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with the BGE model (768-dim) via Workers AI.

    Args:
        texts: The strings to embed.

    Returns:
        One embedding vector per input text, in input order.
    """
    result = await _post(model_embed(), {"text": texts})
    data: list[list[float]] = result.get("data", [])
    return data
