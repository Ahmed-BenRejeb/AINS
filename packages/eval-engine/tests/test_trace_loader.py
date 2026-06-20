"""Trace loading: prefer the full MinIO cassette, fall back to D1 previews."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError
from eval_engine import cassette_store, trace_loader
from pytest_httpx import HTTPXMock
from trace_core import AuditBlock, StepMetadata, TraceRecord


def _record(sequence: int, response: str) -> dict[str, Any]:
    """A full TraceRecord (JSON-mode dict) as the recorder tapes into a cassette."""
    return TraceRecord(
        run_id="run-load",
        step_id=f"s{sequence}",
        sequence=sequence,
        timestamp=datetime.now(UTC),
        kind="llm_call",
        input={"step_key": "sha256:x", "path": "/ai/run/m", "body": {"q": sequence}},
        output={"is_json": True, "body": {"result": {"response": response}}},
        metadata=StepMetadata(model_id="@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        audit=AuditBlock(prev_hash="sha256:0", payload_hash="sha256:1", hmac="ab"),
    ).model_dump(mode="json")


async def test_load_trace_prefers_full_cassette(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a cassette exists, the full records are returned, ordered by sequence."""
    cassette = {
        "version": 1,
        "run_id": "run-load",
        "steps": {},
        "order": [],
        "records": [_record(1, "second"), _record(0, "first")],  # out of order on disk
    }

    def fake_load_blob(key: str) -> bytes:
        assert key == "run-load.json"
        return json.dumps(cassette).encode("utf-8")

    monkeypatch.setattr(cassette_store, "load_blob", fake_load_blob)

    records = await trace_loader.load_trace("run-load")

    assert [r.sequence for r in records] == [0, 1]
    # Full, non-truncated output survived the round-trip.
    assert records[0].output["body"]["result"]["response"] == "first"
    assert records[0].metadata.model_id == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"


async def test_load_trace_falls_back_to_d1_previews(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    """With no cassette, the loader reconstructs from the flight recorder's D1 rows."""

    def missing_blob(key: str) -> bytes:
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    monkeypatch.setattr(cassette_store, "load_blob", missing_blob)
    monkeypatch.setenv("FLIGHT_RECORDER_URL", "http://localhost:8001")
    httpx_mock.add_response(
        url="http://localhost:8001/runs/run-d1",
        json={
            "run_id": "run-d1",
            "manifest": None,
            "trace": [
                {
                    "id": "s0",
                    "run_id": "run-d1",
                    "sequence": 0,
                    "kind": "llm_call",
                    "timestamp_utc": "2026-06-19T00:00:00+00:00",
                    "input_preview": '{"q":1}',
                    "output_preview": '{"a":1}',
                    "prev_hash": "sha256:0",
                    "payload_hash": "sha256:1",
                    "hmac": "ab",
                    "metadata_json": "{}",
                }
            ],
        },
    )

    records = await trace_loader.load_trace("run-d1")

    assert len(records) == 1
    assert records[0].sequence == 0
    assert records[0].input == {"q": 1}


async def test_load_trace_ignores_record_less_cassette(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cassette with no ``records`` (older format) defers to the D1 fallback."""
    cassette = {"version": 1, "run_id": "run-old", "steps": {"sha256:a": {}}, "order": ["sha256:a"]}

    monkeypatch.setattr(
        cassette_store, "load_blob", lambda key: json.dumps(cassette).encode("utf-8")
    )

    assert cassette_store.load_cassette_records("run-old") is None
