"""Tests for the AsyncRecordingTransport: async record/replay, cassette records,
and surviving reuse across several short-lived ``httpx.AsyncClient`` contexts."""

from __future__ import annotations

from typing import Any

import httpx
from flight_recorder.proxy import cassette
from flight_recorder.proxy.llm_proxy import AsyncRecordingTransport
from pytest_httpx import HTTPXMock

CF_URL = (
    "https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/"
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
)

_BODY: dict[str, Any] = {"messages": [{"role": "user", "content": "why?"}], "max_tokens": 1000}
_RESPONSE: dict[str, Any] = {"result": {"response": "because X"}, "success": True}


async def test_async_record_stores_response_record_and_audit(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """Record mode tapes the response, the full TraceRecord, and an audit row."""
    httpx_mock.add_response(json=_RESPONSE)
    transport = AsyncRecordingTransport("run-arec", mode="record")
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(CF_URL, json=_BODY)

    assert response.json() == _RESPONSE
    assert transport.live_call_count == 1
    stored = cassette.load_cassette("run-arec")
    assert len(stored["steps"]) == 1
    assert len(stored["records"]) == 1
    record = stored["records"][0]
    assert record["kind"] == "llm_call"
    assert record["metadata"]["model_id"].endswith("llama-3.3-70b-instruct-fp8-fast")
    assert record["output"]["body"] == _RESPONSE
    assert captured_d1 and captured_d1[0][0] == "trace_records"


async def test_async_transport_survives_multiple_clients(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """One recorder spans two clients (each closes its transport) — chain intact."""
    httpx_mock.add_response(json=_RESPONSE)  # first request
    httpx_mock.add_response(json=_RESPONSE)  # second request
    transport = AsyncRecordingTransport("run-multi", mode="record")

    async with httpx.AsyncClient(transport=transport) as client:
        await client.post(CF_URL, json={"messages": [{"role": "user", "content": "a"}]})
    # The first client closed the inner transport on exit; the recorder must recover.
    async with httpx.AsyncClient(transport=transport) as client:
        await client.post(CF_URL, json={"messages": [{"role": "user", "content": "b"}]})

    assert transport.live_call_count == 2
    assert transport.step_count == 2
    stored = cassette.load_cassette("run-multi")
    assert len(stored["records"]) == 2
    # The audit chain links across the two clients (no genesis reset on reuse).
    assert (
        stored["records"][1]["audit"]["prev_hash"] == stored["records"][0]["audit"]["payload_hash"]
    )


async def test_async_replay_returns_stored_with_zero_live_calls(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
) -> None:
    """Replay serves the cassette response and makes no live async call."""
    request = httpx.Request("POST", CF_URL, json=_BODY)
    step_key = cassette.hash_step_key(cassette.normalize_request(request))
    cassette.save_to_cassette(
        "run-arep",
        step_key,
        {"status_code": 200, "headers": {}, "is_json": True, "body": _RESPONSE},
    )

    transport = AsyncRecordingTransport("run-arep", mode="replay")
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(CF_URL, json=_BODY)

    assert response.json() == _RESPONSE
    assert transport.live_call_count == 0
    assert httpx_mock.get_requests() == []
