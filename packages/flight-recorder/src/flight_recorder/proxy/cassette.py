"""Cassette read/write and request normalization.

A *cassette* is the recorded tape for one run: a JSON blob in MinIO keyed by
``run_id`` that maps a deterministic ``step_key`` to the response that was seen.
In replay mode the recorder hashes the outgoing request, looks the key up here,
and returns the stored response instead of calling the live API.

The hashing itself is **not** redefined here — :func:`normalize_request` and
:func:`hash_step_key` delegate to ``trace_core`` so the cassette key algorithm
has a single source of truth (and a single ``CASSETTE_VERSION`` to bump).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from trace_core import CASSETTE_VERSION, canonical_json
from trace_core import hash_step_key as _trace_hash_step_key
from trace_core import normalize_request as _trace_normalize_request

from ..storage import minio_client


def _cassette_key(run_id: str) -> str:
    """Object key under which a run's cassette blob is stored in MinIO."""
    return f"{run_id}.json"


def _request_to_dict(request: httpx.Request) -> dict[str, Any]:
    """Project an ``httpx.Request`` to the stable dict that identifies it.

    The CF Workers AI model is encoded in the URL path, so the path is part of
    the identity. The body is parsed as JSON when possible (the common case for a
    chat-completion call) so ``trace_core`` can strip volatile fields *inside* it.

    Args:
        request: The outgoing request.

    Returns:
        A JSON-compatible dict of ``method``, ``path`` and ``body``.
    """
    raw = request.content
    body: Any
    if raw:
        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = raw.decode("utf-8", errors="replace")
    else:
        body = None
    return {"method": request.method, "path": request.url.path, "body": body}


def normalize_request(request: httpx.Request) -> str:
    """Normalize a request into a deterministic canonical string.

    Strips ephemeral values (timestamps, request ids, nonces) via
    ``trace_core.normalize_request`` so the same logical request always produces
    the same string regardless of when or where it was issued.

    Args:
        request: The outgoing ``httpx.Request``.

    Returns:
        The canonical, volatility-stripped string for this request.
    """
    return _trace_normalize_request(_request_to_dict(request))


def hash_step_key(normalized: str) -> str:
    """Hash a normalized request into its cassette lookup key (SHA-256).

    Thin re-export of ``trace_core.hash_step_key`` so callers in this package can
    stay within the cassette namespace.

    Args:
        normalized: Output of :func:`normalize_request`.

    Returns:
        The prefixed SHA-256 step key, e.g. ``"sha256:..."``.
    """
    return _trace_hash_step_key(normalized)


def empty_cassette(run_id: str) -> dict[str, Any]:
    """Return a fresh, empty cassette structure for ``run_id``.

    Args:
        run_id: UUID of the run this cassette belongs to.

    Returns:
        A dict with ``version``, ``run_id``, an empty ``steps`` map, an ``order``
        list that records insertion order for positional bisecting, and a
        ``records`` list holding the full :class:`~trace_core.TraceRecord` for
        each step (the non-lossy trace the eval engine reconstructs from).
    """
    return {
        "version": CASSETTE_VERSION,
        "run_id": run_id,
        "steps": {},
        "order": [],
        "records": [],
    }


def load_cassette(run_id: str) -> dict[str, Any]:
    """Load a run's cassette from MinIO, or an empty one if none exists yet.

    Args:
        run_id: UUID of the run.

    Returns:
        The cassette dict (see :func:`empty_cassette` for its shape).
    """
    from botocore.exceptions import ClientError

    try:
        raw = minio_client.load_blob(_cassette_key(run_id))
    except ClientError:
        return empty_cassette(run_id)
    loaded: dict[str, Any] = json.loads(raw)
    return loaded


def save_to_cassette(
    run_id: str,
    step_key: str,
    response: dict[str, Any],
    *,
    record: dict[str, Any] | None = None,
) -> None:
    """Record ``response`` under ``step_key`` in the run's cassette.

    Read-modify-write: loads the existing cassette (or starts an empty one),
    stores the response, preserves first-seen order, optionally appends the
    step's full ``TraceRecord`` to ``records``, and writes it back as canonical
    JSON.

    Args:
        run_id: UUID of the run.
        step_key: Cassette key from :func:`hash_step_key`.
        response: The response payload to store (JSON-serializable). This is what
            replay returns, so its shape must not change (the cassette is the
            ``steps`` map for replay/bisect).
        record: The step's full :class:`~trace_core.TraceRecord` (JSON-mode dict),
            appended to ``records`` for non-lossy trace reconstruction by the eval
            engine. ``None`` skips the append (e.g. tests that only exercise replay).
    """
    cassette = load_cassette(run_id)
    if step_key not in cassette["steps"]:
        cassette["order"].append(step_key)
    cassette["steps"][step_key] = response
    if record is not None:
        cassette.setdefault("records", []).append(record)
    minio_client.store_blob(_cassette_key(run_id), canonical_json(cassette).encode("utf-8"))
