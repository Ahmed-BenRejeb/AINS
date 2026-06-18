"""Tests for cassette normalization, hashing, and load/save round-trips."""

from __future__ import annotations

import httpx
from flight_recorder.proxy import cassette

CF_URL = (
    "https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/"
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
)


def _request(body: dict[str, object]) -> httpx.Request:
    return httpx.Request("POST", CF_URL, json=body)


def test_normalize_request_is_deterministic() -> None:
    """The same request normalizes identically every time."""
    body = {"messages": [{"role": "user", "content": "why?"}], "max_tokens": 1000}
    first = cassette.normalize_request(_request(body))
    for _ in range(50):
        assert cassette.normalize_request(_request(body)) == first


def test_normalize_strips_volatile_fields() -> None:
    """Ephemeral fields (timestamp, request_id, nonce) do not change the key."""
    body = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}
    noisy = {**body, "timestamp": "2026-06-18T00:00:00Z", "request_id": "r-1", "nonce": "x"}
    assert cassette.normalize_request(_request(body)) == cassette.normalize_request(_request(noisy))


def test_different_inputs_hash_differently() -> None:
    """Meaningfully different requests must not collide."""
    a = cassette.hash_step_key(cassette.normalize_request(_request({"max_tokens": 10})))
    b = cassette.hash_step_key(cassette.normalize_request(_request({"max_tokens": 20})))
    assert a != b


def test_different_model_path_hashes_differently() -> None:
    """The model in the URL path is part of the request identity."""
    body = {"messages": [], "max_tokens": 1}
    other_model = CF_URL.replace("llama-3.3-70b-instruct-fp8-fast", "llama-guard-3-8b")
    key_a = cassette.hash_step_key(
        cassette.normalize_request(httpx.Request("POST", CF_URL, json=body))
    )
    key_b = cassette.hash_step_key(
        cassette.normalize_request(httpx.Request("POST", other_model, json=body))
    )
    assert key_a != key_b


def test_hash_step_key_is_prefixed_sha256() -> None:
    """hash_step_key returns a 'sha256:' + 64-hex digest."""
    key = cassette.hash_step_key(cassette.normalize_request(_request({"max_tokens": 1})))
    assert key.startswith("sha256:")
    assert len(key) == len("sha256:") + 64


def test_load_missing_cassette_returns_empty(fake_blobs: dict[str, bytes]) -> None:
    """Loading a run with no stored cassette yields a fresh empty structure."""
    loaded = cassette.load_cassette("run-unknown")
    assert loaded["steps"] == {}
    assert loaded["order"] == []
    assert loaded["run_id"] == "run-unknown"


def test_save_then_load_round_trips(fake_blobs: dict[str, bytes]) -> None:
    """A saved step is retrievable and preserves insertion order."""
    cassette.save_to_cassette("run-1", "sha256:aaa", {"body": 1})
    cassette.save_to_cassette("run-1", "sha256:bbb", {"body": 2})
    loaded = cassette.load_cassette("run-1")
    assert loaded["steps"]["sha256:aaa"] == {"body": 1}
    assert loaded["steps"]["sha256:bbb"] == {"body": 2}
    assert loaded["order"] == ["sha256:aaa", "sha256:bbb"]
