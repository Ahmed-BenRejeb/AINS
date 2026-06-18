"""Tests for the canonical hashing utilities.

The cassette system depends on these being deterministic and stable, so the
tests focus on: same input always yields the same key, key order and volatile
fields do not affect the key, and different inputs yield different keys.
"""

from __future__ import annotations

from typing import Any

from trace_core import (
    HASH_PREFIX,
    canonical_json,
    hash_step_key,
    normalize_request,
    sha256_hex,
)


def _request() -> dict[str, Any]:
    return {
        "model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "messages": [{"role": "user", "content": "Why did the incident happen?"}],
        "max_tokens": 1000,
    }


def test_normalize_request_is_deterministic() -> None:
    """The same request normalizes to the same string every time."""
    req = _request()
    first = normalize_request(req)
    for _ in range(100):
        assert normalize_request(req) == first


def test_normalize_request_is_key_order_independent() -> None:
    """Dicts that differ only in key insertion order normalize identically."""
    a = {"model": "m", "max_tokens": 10, "messages": []}
    b = {"messages": [], "max_tokens": 10, "model": "m"}
    assert normalize_request(a) == normalize_request(b)


def test_normalize_request_strips_volatile_fields() -> None:
    """Volatile fields (timestamps, request ids, nonces) do not affect the result."""
    base = _request()
    noisy = {
        **base,
        "timestamp": "2026-06-18T12:00:00Z",
        "request_id": "req-abc",
        "nonce": "xyz",
    }
    assert normalize_request(base) == normalize_request(noisy)


def test_normalize_request_strips_volatile_fields_case_insensitively() -> None:
    """Volatile keys are matched case-insensitively."""
    base = _request()
    noisy = {**base, "Request_ID": "req-abc", "TIMESTAMP": "now"}
    assert normalize_request(base) == normalize_request(noisy)


def test_normalize_request_strips_nested_volatile_fields() -> None:
    """Volatile fields are stripped recursively, including inside lists."""
    clean = {"messages": [{"role": "user", "content": "hi"}]}
    noisy = {
        "messages": [{"role": "user", "content": "hi", "trace_id": "t-1"}],
        "span_id": "s-1",
    }
    assert normalize_request(clean) == normalize_request(noisy)


def test_different_inputs_produce_different_hashes() -> None:
    """Meaningfully different requests must not collide."""
    a = hash_step_key(normalize_request(_request()))
    b = hash_step_key(normalize_request({**_request(), "max_tokens": 500}))
    assert a != b


def test_hash_step_key_is_deterministic_and_prefixed() -> None:
    """hash_step_key is stable and returns a prefixed SHA-256 hex digest."""
    normalized = normalize_request(_request())
    key = hash_step_key(normalized)
    assert key == hash_step_key(normalized)
    assert key.startswith(HASH_PREFIX)
    # "sha256:" + 64 hex chars
    assert len(key) == len(HASH_PREFIX) + 64


def test_hash_step_key_known_value_is_stable() -> None:
    """A frozen golden value guards against accidental changes to the algorithm.

    If this assertion ever fails, the cassette key algorithm changed and
    CASSETTE_VERSION must be bumped (existing cassettes are invalidated).
    """
    assert hash_step_key("hello") == sha256_hex("hello")
    assert sha256_hex("hello") == (
        "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_canonical_json_sorts_keys_and_is_compact() -> None:
    """canonical_json produces sorted-key, whitespace-free JSON."""
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
