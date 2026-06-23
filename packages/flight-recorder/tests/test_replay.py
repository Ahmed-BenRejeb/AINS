"""Tests for deterministic replay: record once, replay with zero live calls."""

from __future__ import annotations

from typing import Any

import httpx
from flight_recorder.proxy.llm_proxy import RecordingTransport
from flight_recorder.replay.engine import replay_run
from pytest_httpx import HTTPXMock

CF_URL = (
    "https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/"
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
)

_BODY: dict[str, Any] = {
    "messages": [{"role": "user", "content": "root cause?"}],
    "max_tokens": 512,
}
_RESPONSE: dict[str, Any] = {"result": {"response": "disk full"}, "success": True}


def _agent(client: httpx.Client) -> dict[str, Any]:
    """A tiny agent that makes one CF Workers AI call."""
    body: dict[str, Any] = client.post(CF_URL, json=_BODY).json()
    return body


def test_replay_produces_zero_live_calls(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """Record the agent once, then replay it with no live API calls and no divergence."""
    # ── Record phase: the one live call is mocked and taped. ──
    httpx_mock.add_response(json=_RESPONSE)
    with httpx.Client(transport=RecordingTransport("run-replay", mode="record")) as client:
        assert _agent(client) == _RESPONSE
    assert len(httpx_mock.get_requests()) == 1

    # ── Replay phase: served entirely from the cassette. ──
    result = replay_run("run-replay", _agent)

    assert result.live_call_count == 0
    assert result.diverged is False
    assert result.divergences == []
    assert result.recorded_steps == 1
    assert result.is_clean is True
    # Still exactly one request total — replay added none.
    assert len(httpx_mock.get_requests()) == 1


def test_replay_reports_divergence_on_cassette_miss(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
) -> None:
    """An agent that asks for an unrecorded request is reported as diverged, not run live."""
    # Cassette for this run is empty, so the agent's request is a miss.
    result = replay_run("run-missing", _agent)

    assert result.live_call_count == 0
    assert result.diverged is True
    assert result.divergences[0].reason == "request not present in cassette"
    assert httpx_mock.get_requests() == []


def _branching_agent(client: httpx.Client) -> dict[str, Any]:
    """An agent whose SECOND request depends on the FIRST response (branches)."""
    first = client.post(
        CF_URL, json={"messages": [{"role": "user", "content": "diagnose"}], "max_tokens": 256}
    ).json()
    answer = first.get("result", {}).get("response", "")
    follow = "deep dive: disk" if "disk" in answer else "deep dive: other"
    second: dict[str, Any] = client.post(
        CF_URL, json={"messages": [{"role": "user", "content": follow}], "max_tokens": 256}
    ).json()
    return second


def test_replay_injection_makes_agent_take_a_new_path(
    httpx_mock: HTTPXMock,
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """Divergence editing (UC2 §3.4): overriding a recorded response reroutes the agent.

    Record the branching agent (first answer mentions "disk" → it asks the "disk"
    follow-up). On replay, inject a different first response at step 0; the agent now
    takes the "other" branch, whose request was never recorded → a divergence.
    """
    httpx_mock.add_response(json={"result": {"response": "disk full"}, "success": True})
    httpx_mock.add_response(json={"result": {"response": "ok"}, "success": True})
    with httpx.Client(transport=RecordingTransport("run-inject", mode="record")) as client:
        _branching_agent(client)

    # Clean replay first: no injection → both steps served, no divergence.
    clean = replay_run("run-inject", _branching_agent)
    assert clean.is_clean is True
    assert clean.injected_steps == []

    # Inject a different response at step 0 → the agent branches to an unrecorded request.
    override = {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "is_json": True,
        "body": {"result": {"response": "network issue"}, "success": True},
    }
    diverged = replay_run("run-inject", _branching_agent, inject={0: override})
    assert diverged.injected_steps == [0]
    assert diverged.diverged is True
    assert diverged.live_call_count == 0  # the new path is a cassette miss, never live
    assert diverged.divergences[0].reason == "request not present in cassette"


def test_replay_without_agent_validates_cassette(
    fake_blobs: dict[str, bytes],
) -> None:
    """A no-op replay (no agent) still loads the cassette and proves zero live calls."""
    from flight_recorder.proxy import cassette

    cassette.save_to_cassette("run-noop", "sha256:aaa", {"body": 1})
    result = replay_run("run-noop")

    assert result.recorded_steps == 1
    assert result.live_call_count == 0
    assert result.is_clean is True
