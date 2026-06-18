"""Canonical hashing utilities for the flight-recorder cassette system.

These functions turn a request into a stable lookup key. In ``replay`` mode the
flight recorder hashes the outgoing request and looks the key up in the cassette
to return the recorded response instead of calling the live API.

**Stability is a hard contract.** :func:`hash_step_key` is the cassette lookup
key — if the same logical request stops producing the same key, every existing
cassette breaks. Any change to normalization or hashing here MUST bump
:data:`trace_core.constants.CASSETTE_VERSION`.

These functions are pure: deterministic, no I/O, no global state.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .constants import HASH_ALGORITHM, HASH_PREFIX, VOLATILE_REQUEST_FIELDS


def _strip_volatile(value: Any) -> Any:
    """Recursively drop volatile keys so they never influence the hash.

    Volatile fields (timestamps, request IDs, nonces — see
    :data:`~trace_core.constants.VOLATILE_REQUEST_FIELDS`) change on
    every otherwise-identical request and would defeat cassette lookup. Matching
    is case-insensitive on the key. Non-mapping values are returned unchanged;
    lists are processed element-wise.

    Args:
        value: Any JSON-compatible value drawn from the request.

    Returns:
        The same structure with volatile mapping keys removed.
    """
    if isinstance(value, Mapping):
        return {
            key: _strip_volatile(val)
            for key, val in value.items()
            if str(key).lower() not in VOLATILE_REQUEST_FIELDS
        }
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value


def canonical_json(obj: Any) -> str:
    """Serialize an object to canonical JSON: sorted keys, no insignificant whitespace.

    Canonicalization makes two semantically equal payloads produce byte-identical
    strings regardless of key order or formatting, which is what makes hashing
    deterministic.

    Args:
        obj: Any JSON-serializable value.

    Returns:
        A canonical JSON string (sorted keys, compact separators, ``ensure_ascii``).
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def normalize_request(request: Mapping[str, Any]) -> str:
    """Normalize a request into a stable canonical string for hashing.

    Strips volatile fields, then canonicalizes. The same logical request always
    normalizes to the same string; two different requests normalize differently
    (unless they differ only in volatile fields, which is intentional).

    Args:
        request: The request payload (e.g. an LLM chat-completion body) as a
            mapping of JSON-compatible values.

    Returns:
        The canonical, volatility-stripped JSON string for this request.
    """
    return canonical_json(_strip_volatile(dict(request)))


def sha256_hex(data: str) -> str:
    """Return the SHA-256 hex digest of a string, prefixed (e.g. ``sha256:...``).

    Args:
        data: The UTF-8 string to hash.

    Returns:
        The digest as ``"{HASH_PREFIX}{hexdigest}"``.
    """
    digest = hashlib.new(HASH_ALGORITHM, data.encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"


def hash_step_key(normalized: str) -> str:
    """Hash a normalized request into the cassette lookup key.

    This is the key under which a recorded response is stored and later found in
    replay mode. It MUST be deterministic and stable across runs and machines.

    Args:
        normalized: Output of :func:`normalize_request`.

    Returns:
        The cassette step key, e.g. ``"sha256:abc123..."``.
    """
    return sha256_hex(normalized)
