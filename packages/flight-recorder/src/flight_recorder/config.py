"""Environment-driven configuration for the flight recorder.

Centralises every value the recorder reads from the environment so no other
module hardcodes an env-var name, URL, or default. ``FLIGHT_MODE`` is the single
switch that controls record/replay/passthrough behaviour throughout the package.
"""

from __future__ import annotations

import os
from typing import cast, get_args

from trace_core import HASH_PREFIX, FlightMode

# ─── Flight mode (record | replay | passthrough) ───────────────────────────────

_VALID_MODES: frozenset[str] = frozenset(get_args(FlightMode))
DEFAULT_FLIGHT_MODE: FlightMode = "record"
"""Default mode when ``FLIGHT_MODE`` is unset (matches ``.env.example``)."""


def resolve_mode(mode: FlightMode | None = None) -> FlightMode:
    """Resolve the operating mode, falling back to the ``FLIGHT_MODE`` env var.

    Args:
        mode: Explicit override; when ``None`` the ``FLIGHT_MODE`` env var (then
            :data:`DEFAULT_FLIGHT_MODE`) is used.

    Returns:
        A validated :data:`~trace_core.FlightMode` literal.

    Raises:
        ValueError: If the resolved value is not a recognised flight mode.
    """
    raw = mode if mode is not None else os.environ.get("FLIGHT_MODE", DEFAULT_FLIGHT_MODE)
    if raw not in _VALID_MODES:
        raise ValueError(f"invalid FLIGHT_MODE {raw!r}; expected one of {sorted(_VALID_MODES)}")
    return cast(FlightMode, raw)


# ─── Cloudflare Workers AI endpoint detection ──────────────────────────────────

CF_API_HOST = "api.cloudflare.com"
"""Host of the Cloudflare API; only requests to this host are candidates for
interception (see :func:`is_cf_workers_ai_url`)."""

CF_AI_RUN_PATH_MARKER = "/ai/run/"
"""Path fragment that identifies a Workers AI ``run`` call:
``/client/v4/accounts/{id}/ai/run/{model}``."""


def is_cf_workers_ai_url(url: object) -> bool:
    """Return ``True`` if ``url`` is a Cloudflare Workers AI ``run`` endpoint.

    Only these URLs are recorded/replayed; anything else passes straight through
    so the transport stays transparent to unrelated traffic.

    Args:
        url: An ``httpx.URL`` (or anything with ``.host``/``.path``).

    Returns:
        Whether the URL targets ``.../ai/run/{model}`` on the Cloudflare API.
    """
    host = getattr(url, "host", "")
    path = getattr(url, "path", "")
    return host == CF_API_HOST and CF_AI_RUN_PATH_MARKER in path


# ─── Audit chain ───────────────────────────────────────────────────────────────

GENESIS_PREV_HASH: str = f"{HASH_PREFIX}{'0' * 64}"
"""``prev_hash`` of the first record in a run's audit chain (all-zero genesis).

See :class:`trace_core.AuditBlock` — the genesis link has no predecessor.
"""

AUDIT_HMAC_KEY_ENV = "AUDIT_HMAC_KEY"
"""Env var holding the secret that HMAC-signs every audit record."""

TRACE_RECORDS_TABLE = "trace_records"
"""Cloudflare D1 table the audit chain is written to (see ``d1-schema.sql``)."""

RUN_MANIFESTS_TABLE = "run_manifests"
"""Cloudflare D1 table holding one summary row per recorded run."""
