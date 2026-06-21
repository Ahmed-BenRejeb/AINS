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

import asyncio
import contextlib
import contextvars
import json
import logging
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

logger = logging.getLogger("atlassian_remote.cf_ai_client")

# CF Workers AI retry policy (root CLAUDE.md §10): the free tier rate-limits under
# heavy load. 429 → long backoff, a few times; transient 5xx → short backoff.
_RATE_LIMIT_STATUS = 429
_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BACKOFF_SECONDS = 30.0
_SERVER_ERROR_MAX_RETRIES = 2
_SERVER_ERROR_BACKOFF_SECONDS = 5.0


def _retry_delay(status_code: int, attempt: int) -> float | None:
    """Backoff (seconds) for a retryable CF Workers AI status, or ``None``.

    Args:
        status_code: HTTP status from the failed response.
        attempt: Retries already performed (0 on the first failure).

    Returns:
        Seconds to wait before the next retry, or ``None`` when the status is not
        retryable or its retry budget is exhausted.
    """
    if status_code == _RATE_LIMIT_STATUS:
        return _RATE_LIMIT_BACKOFF_SECONDS if attempt < _RATE_LIMIT_MAX_RETRIES else None
    if 500 <= status_code < 600:
        return _SERVER_ERROR_BACKOFF_SECONDS if attempt < _SERVER_ERROR_MAX_RETRIES else None
    return None


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

    Retries on rate limiting and transient server errors (root CLAUDE.md §10):
    a ``429`` waits ``30s`` and retries up to 3 times; a ``5xx`` waits ``5s`` and
    retries up to 2 times. Other statuses (and exhausted budgets) raise
    :class:`httpx.HTTPStatusError`. Waits use :func:`asyncio.sleep` so the event
    loop stays free.

    Args:
        model: The CF model id (e.g. ``@cf/meta/llama-3.3-70b-instruct-fp8-fast``).
        payload: The JSON request body.

    Returns:
        The ``result`` object from the Workers AI response envelope.

    Raises:
        httpx.HTTPStatusError: On a non-retryable status or once retries are spent.
    """
    attempt = 0
    while True:
        async with httpx.AsyncClient(
            timeout=CF_TIMEOUT_SECONDS, transport=_active_transport.get()
        ) as client:
            response = await client.post(
                f"{cf_ai_url()}/{model}",
                headers={"Authorization": f"Bearer {cf_api_token()}"},
                json=payload,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            delay = _retry_delay(exc.response.status_code, attempt)
            if delay is None:
                raise
            attempt += 1
            logger.warning(
                "CF Workers AI %s for model %s; retry %d after %.0fs backoff",
                exc.response.status_code,
                model,
                attempt,
                delay,
            )
            await asyncio.sleep(delay)
            continue
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
