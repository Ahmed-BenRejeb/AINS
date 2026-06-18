"""Shared Cloudflare Workers AI client used by every grader.

All LLM, embedding, and safety calls in the eval engine go through here — never
the Anthropic or OpenAI SDKs (root CLAUDE.md Section 7). Three entry points:

* :func:`cf_ai_chat`   — chat completion (the LLM judge).
* :func:`cf_ai_embed`  — BGE embeddings (drift detection).
* :func:`cf_ai_safety` — Llama Guard 3 safety classification.

Tests mock these functions directly (``monkeypatch`` the module attribute), so no
real network call is made.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import (
    CF_TIMEOUT_SECONDS,
    DEFAULT_MAX_TOKENS,
    cf_ai_url,
    cf_api_token,
    model_embed,
    model_main,
    model_safety,
)
from .models import SafetyResult

_SAFE_TOKEN = "safe"
_UNSAFE_TOKEN = "unsafe"


async def _post(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST a payload to a Workers AI model and return its ``result`` object.

    Args:
        model: The CF model id (e.g. ``@cf/meta/llama-3.3-70b-instruct-fp8-fast``).
        payload: The JSON request body.

    Returns:
        The ``result`` object from the Workers AI response envelope.
    """
    async with httpx.AsyncClient(timeout=CF_TIMEOUT_SECONDS) as client:
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
        model: Model id; defaults to ``CF_AI_MODEL_MAIN``.
        max_tokens: Completion token budget.

    Returns:
        The assistant's response text.
    """
    result = await _post(
        model or model_main(),
        {"messages": messages, "max_tokens": max_tokens},
    )
    response: str = result.get("response", "")
    return response


async def cf_ai_embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with the BGE model (768-dim) via Workers AI.

    Args:
        texts: The strings to embed.

    Returns:
        One embedding vector per input text.
    """
    result = await _post(model_embed(), {"text": texts})
    data: list[list[float]] = result.get("data", [])
    return data


async def cf_ai_safety(text: str) -> SafetyResult:
    """Classify text with Llama Guard 3 and return a structured safety result.

    Llama Guard returns ``safe`` or ``unsafe`` followed by the hazard categories
    that fired (e.g. ``unsafe\\nS1,S14``). This parses that into a
    :class:`~eval_engine.models.SafetyResult`.

    Args:
        text: The content to classify.

    Returns:
        A :class:`SafetyResult` with ``safe``, a 0/1 ``score``, and any categories.
    """
    result = await _post(
        model_safety(),
        {"messages": [{"role": "user", "content": text}]},
    )
    raw = str(result.get("response", "")).strip()
    lowered = raw.lower()
    is_unsafe = lowered.startswith(_UNSAFE_TOKEN) or (
        _UNSAFE_TOKEN in lowered and _SAFE_TOKEN not in lowered.split()
    )
    categories: list[str] = []
    if is_unsafe:
        # Categories follow on the next line / after whitespace, comma-separated.
        tail = raw[len(_UNSAFE_TOKEN) :] if lowered.startswith(_UNSAFE_TOKEN) else raw
        categories = [
            token.strip() for token in tail.replace("\n", ",").split(",") if token.strip()
        ]
    return SafetyResult(safe=not is_unsafe, score=0.0 if is_unsafe else 1.0, categories=categories)
