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
        model: Model id; defaults to ``CF_AI_MODEL_MAIN`` (Llama 3.3 70B).
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
        One embedding vector per input text, in input order.
    """
    result = await _post(model_embed(), {"text": texts})
    data: list[list[float]] = result.get("data", [])
    return data
