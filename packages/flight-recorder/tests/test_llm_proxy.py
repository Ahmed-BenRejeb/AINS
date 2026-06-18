"""Tests for the RecordingTransport: record stores, replay returns, no live calls."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from flight_recorder.exceptions import CassetteMissError
from flight_recorder.proxy import cassette
from flight_recorder.proxy.llm_proxy import RecordingTransport
from pytest_httpx import HTTPXMock

CF_URL = (
    "https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/"
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
)

_BODY: dict[str, Any] = {"messages": [{"role": "user", "content": "why?"}], "max_tokens": 1000}
_RESPONSE: dict[str, Any] = {"result": {"response": "because X"}, "success": True}


def test_record_mode_stores_response_and_writes_audit(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """Record mode forwards the call, stores the response, and writes an audit record."""
    httpx_mock.add_response(json=_RESPONSE)
    transport = RecordingTransport("run-rec", mode="record")
    with httpx.Client(transport=transport) as client:
        response = client.post(CF_URL, json=_BODY)

    assert response.json() == _RESPONSE
    assert transport.live_call_count == 1
    stored = cassette.load_cassette("run-rec")
    assert len(stored["steps"]) == 1
    assert captured_d1 and captured_d1[0][0] == "trace_records"


def test_replay_mode_returns_stored_response_with_zero_live_calls(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
) -> None:
    """Replay mode serves the cassette response and makes no live API call."""
    request = httpx.Request("POST", CF_URL, json=_BODY)
    step_key = cassette.hash_step_key(cassette.normalize_request(request))
    cassette.save_to_cassette(
        "run-rep",
        step_key,
        {"status_code": 200, "headers": {}, "is_json": True, "body": _RESPONSE},
    )

    transport = RecordingTransport("run-rep", mode="replay")
    with httpx.Client(transport=transport) as client:
        response = client.post(CF_URL, json=_BODY)

    assert response.json() == _RESPONSE
    assert transport.live_call_count == 0
    assert httpx_mock.get_requests() == []


def test_replay_mode_raises_on_cassette_miss(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
) -> None:
    """An unrecorded request raises rather than escaping to the network."""
    transport = RecordingTransport("run-empty", mode="replay")
    with httpx.Client(transport=transport) as client:
        with pytest.raises(CassetteMissError):
            client.post(CF_URL, json=_BODY)
    assert transport.live_call_count == 0
    assert httpx_mock.get_requests() == []


def test_non_cf_request_passes_through_untouched(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
) -> None:
    """Requests that are not CF Workers AI calls are forwarded, never recorded."""
    httpx_mock.add_response(json={"ok": True})
    transport = RecordingTransport("run-other", mode="record")
    with httpx.Client(transport=transport) as client:
        response = client.get("https://example.com/health")

    assert response.json() == {"ok": True}
    assert transport.live_call_count == 1
    assert cassette.load_cassette("run-other")["steps"] == {}
