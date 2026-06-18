"""Tests for the @record_tool decorator: record stores, replay never calls live."""

from __future__ import annotations

from typing import Any

import pytest
from flight_recorder.exceptions import CassetteMissError
from flight_recorder.proxy.mcp_interceptor import record_tool
from pydantic import BaseModel


def test_record_then_replay_does_not_call_real_function(
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """Replay returns the recorded result without invoking the wrapped function."""
    calls: list[Any] = []

    def fetch_incident(incident_id: int) -> dict[str, Any]:
        calls.append(("real", incident_id))
        return {"id": incident_id, "status": "open"}

    recorded = record_tool("run-tool", mode="record")(fetch_incident)
    assert recorded(7) == {"id": 7, "status": "open"}
    assert calls == [("real", 7)]
    assert captured_d1 and captured_d1[0][1]["kind"] == "tool_call"

    replayed = record_tool("run-tool", mode="replay")(fetch_incident)
    assert replayed(7) == {"id": 7, "status": "open"}
    # The real function was not called a second time.
    assert calls == [("real", 7)]


def test_replay_miss_raises(fake_blobs: dict[str, bytes]) -> None:
    """Replaying a call that was never recorded raises CassetteMissError."""

    def fetch(x: int) -> int:
        return x

    replayed = record_tool("run-empty", mode="replay")(fetch)
    with pytest.raises(CassetteMissError):
        replayed(123)


def test_pydantic_results_are_recorded_as_json(
    fake_blobs: dict[str, bytes],
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """Pydantic structured outputs round-trip through the cassette as JSON dicts."""

    class Draft(BaseModel):
        cause: str
        confidence: float

    def analyze() -> Draft:
        return Draft(cause="oom", confidence=0.9)

    recorded = record_tool("run-pyd", mode="record")(analyze)
    assert isinstance(recorded(), Draft)

    replayed = record_tool("run-pyd", mode="replay")(analyze)
    # In replay the recorded JSON dict is returned, not a re-instantiated model.
    replayed_result: Any = replayed()
    assert replayed_result == {"cause": "oom", "confidence": 0.9}


def test_passthrough_mode_calls_without_recording(fake_blobs: dict[str, bytes]) -> None:
    """Passthrough calls the real function and records nothing."""
    from flight_recorder.proxy import cassette

    def ping() -> str:
        return "pong"

    wrapped = record_tool("run-pass", mode="passthrough")(ping)
    assert wrapped() == "pong"
    assert cassette.load_cassette("run-pass")["steps"] == {}
