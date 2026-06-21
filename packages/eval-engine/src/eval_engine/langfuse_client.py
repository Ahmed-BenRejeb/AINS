"""Shared Langfuse observability client (UC1).

A single, lazily-initialised :class:`langfuse.Langfuse` client is shared across the
service so every LLM call lands in one Langfuse project. Initialisation is
env-driven (``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` / ``LANGFUSE_HOST``)
and **best-effort**: when those vars are unset the helpers degrade to no-ops, so
tracing never breaks request handling (the project's "observability must never
fail the request" rule, mirroring best-effort recording + Jira filing).

This package pins ``langfuse>=4.9.1`` (the v4 SDK). The v2 ``langfuse.generation()``
/ ``langfuse.span()`` factory methods were removed; v4 uses
``Langfuse.start_observation(..., as_type=...)`` and ends an observation with
``.update(output=...)`` then ``.end()``. These helpers wrap that surface.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from langfuse import Langfuse, LangfuseGeneration, LangfuseSpan

logger = logging.getLogger("eval_engine.langfuse")

_Observation = LangfuseGeneration | LangfuseSpan


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    """Return the shared Langfuse client, or ``None`` when tracing is unconfigured.

    The client is constructed once (``lru_cache``) from the ``LANGFUSE_*`` env
    vars. If any of public key / secret key / host is missing, tracing is treated
    as disabled and ``None`` is returned so the instrumentation helpers no-op.

    Returns:
        The shared :class:`langfuse.Langfuse` client, or ``None`` if unconfigured.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    # Deliver to the internal Langfuse endpoint when set: the public host sits
    # behind a Cloudflare bot challenge that 403s the SDK (root CLAUDE.md §0), so
    # ``LANGFUSE_HOST_INTERNAL`` (e.g. http://127.0.0.1:3000) is preferred for
    # server-side delivery, falling back to ``LANGFUSE_HOST``.
    host = os.environ.get("LANGFUSE_HOST_INTERNAL") or os.environ.get("LANGFUSE_HOST")
    if not (public_key and secret_key and host):
        return None
    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def init_langfuse() -> Langfuse | None:
    """Initialise Langfuse tracing at service startup and log the outcome.

    Returns:
        The shared client (tracing enabled), or ``None`` (tracing disabled).
    """
    client = get_langfuse()
    if client is None:
        logger.info("Langfuse tracing disabled (LANGFUSE_* env not configured)")
    else:
        logger.info("Langfuse tracing enabled (host=%s)", os.environ.get("LANGFUSE_HOST"))
    return client


def start_generation(name: str, model: str, input: Any) -> LangfuseGeneration | None:
    """Start a Langfuse generation observation for one LLM call.

    Args:
        name: Human-readable observation name (e.g. ``"llm-judge"``).
        model: The model id the call targets.
        input: The request payload to record (e.g. the chat messages).

    Returns:
        The started :class:`LangfuseGeneration`, or ``None`` when tracing is off.
    """
    client = get_langfuse()
    if client is None:
        return None
    return client.start_observation(name=name, as_type="generation", model=model, input=input)


def start_span(name: str, input: Any) -> LangfuseSpan | None:
    """Start a Langfuse span observation for one non-LLM unit of work.

    Args:
        name: Human-readable observation name (e.g. ``"xqdrant-search"``).
        input: The operation input to record.

    Returns:
        The started :class:`LangfuseSpan`, or ``None`` when tracing is off.
    """
    client = get_langfuse()
    if client is None:
        return None
    return client.start_observation(name=name, as_type="span", input=input)


def end_observation(observation: _Observation | None, output: Any) -> None:
    """Record an observation's output and end it (no-op when ``observation`` is None).

    Args:
        observation: The observation returned by :func:`start_generation` /
            :func:`start_span`, or ``None`` when tracing is disabled.
        output: The result to attach to the observation before ending it.
    """
    if observation is None:
        return
    observation.update(output=output)
    observation.end()
