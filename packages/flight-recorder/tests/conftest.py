"""Shared fixtures for flight-recorder tests.

Everything external is faked: MinIO blob storage becomes an in-memory dict, the
Cloudflare D1 ``insert`` is captured in a list, and ``AUDIT_HMAC_KEY`` is set to a
test secret. No fixture touches a real network — HTTP is mocked per-test with the
``httpx_mock`` fixture from ``pytest-httpx``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from botocore.exceptions import ClientError
from flight_recorder.proxy import mcp_interceptor
from flight_recorder.storage import d1_client, minio_client


@pytest.fixture(autouse=True)
def audit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a deterministic HMAC secret for every test."""
    monkeypatch.setenv("AUDIT_HMAC_KEY", "test-secret-key-0123456789abcdef")


@pytest.fixture(autouse=True)
def reset_interceptor_state() -> Iterator[None]:
    """Clear the tool interceptor's per-run audit-chain heads between tests."""
    mcp_interceptor._PREV_HASH.clear()
    mcp_interceptor._SEQUENCE.clear()
    yield
    mcp_interceptor._PREV_HASH.clear()
    mcp_interceptor._SEQUENCE.clear()


@pytest.fixture
def fake_blobs(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """Replace MinIO with an in-memory ``key -> bytes`` store."""
    store: dict[str, bytes] = {}

    def _store(key: str, data: bytes) -> None:
        store[key] = data

    def _load(key: str) -> bytes:
        if key not in store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return store[key]

    monkeypatch.setattr(minio_client, "store_blob", _store)
    monkeypatch.setattr(minio_client, "load_blob", _load)
    return store


@pytest.fixture
def captured_d1(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Capture every ``d1_client.insert`` call instead of hitting Cloudflare D1."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def _insert(table: str, record: dict[str, Any]) -> None:
        calls.append((table, record))

    monkeypatch.setattr(d1_client, "insert", _insert)
    return calls
