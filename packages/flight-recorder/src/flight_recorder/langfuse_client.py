"""Shared Langfuse observability client (UC2).

A single, lazily-initialised :class:`langfuse.Langfuse` client for the flight
recorder service. Initialisation is env-driven (``LANGFUSE_PUBLIC_KEY`` /
``LANGFUSE_SECRET_KEY`` / ``LANGFUSE_HOST``) and **best-effort**: when those vars
are unset it degrades to a no-op so tracing never breaks request handling.

The recorder taps LLM calls through its recording transport (UC2's core job), so
it has no per-call generation to instrument here; :func:`init_langfuse` simply
wires up the client at startup so the service registers with Langfuse.

This package pins ``langfuse>=4.9.1`` (the v4 SDK).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from langfuse import Langfuse

logger = logging.getLogger("flight_recorder.langfuse")


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    """Return the shared Langfuse client, or ``None`` when tracing is unconfigured.

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
