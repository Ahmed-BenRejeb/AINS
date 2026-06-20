"""Load a run's trace from the flight recorder for evaluation.

The eval API is given a ``run_id``; the full trace lives in the flight recorder
(UC2). Two sources, in order of fidelity:

1. **The MinIO cassette** (``{run_id}.json``) — the flight recorder tapes every
   step's *full* :class:`~trace_core.TraceRecord` there, so this is the non-lossy
   source. Preferred whenever the cassette exists (:mod:`cassette_store`).
2. **D1 previews** (fallback) — ``GET {FLIGHT_RECORDER_URL}/runs/{run_id}``
   returns the ``trace_records`` rows, whose input/output are 500-char previews.
   Used only when the cassette is absent (e.g. an older record-less run). A
   truncated preview falls back to a wrapper dict rather than failing the load.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from trace_core import AuditBlock, StepKind, StepMetadata, TraceRecord

from . import cassette_store

_DEFAULT_FLIGHT_URL = "https://flight.ahmedxsaad.me"
_LOAD_TIMEOUT_SECONDS = 30.0
_VALID_KINDS: frozenset[str] = frozenset({"llm_call", "tool_call", "decision", "state_snapshot"})


def _flight_url() -> str:
    return os.environ.get("FLIGHT_RECORDER_URL", _DEFAULT_FLIGHT_URL).rstrip("/")


def _parse_preview(raw: object) -> dict[str, Any]:
    """Parse a D1 preview string into a dict, tolerating truncation."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"preview": raw}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _row_to_record(row: dict[str, Any]) -> TraceRecord:
    """Map one ``trace_records`` D1 row to a ``TraceRecord``."""
    metadata_raw = _parse_preview(row.get("metadata_json"))
    kind = row.get("kind", "decision")
    step_kind: StepKind = kind if kind in _VALID_KINDS else "decision"
    timestamp_raw = row.get("timestamp_utc")
    try:
        timestamp = datetime.fromisoformat(str(timestamp_raw))
    except (TypeError, ValueError):
        timestamp = datetime.now(UTC)
    return TraceRecord(
        run_id=str(row.get("run_id", "")),
        step_id=str(row.get("id", "")),
        sequence=int(row.get("sequence", 0)),
        timestamp=timestamp,
        kind=step_kind,
        input=_parse_preview(row.get("input_preview")),
        output=_parse_preview(row.get("output_preview")),
        metadata=StepMetadata.model_validate(metadata_raw) if metadata_raw else StepMetadata(),
        audit=AuditBlock(
            prev_hash=str(row.get("prev_hash", "")),
            payload_hash=str(row.get("payload_hash", "")),
            hmac=str(row.get("hmac", "")),
        ),
    )


async def load_trace(run_id: str) -> list[TraceRecord]:
    """Fetch and reconstruct the ordered trace for a run.

    Prefers the full MinIO cassette (non-lossy); falls back to the flight
    recorder's D1 previews when no cassette exists for the run.

    Args:
        run_id: UUID of the run.

    Returns:
        The run's steps as ``TraceRecord`` objects, ordered by sequence.
    """
    cassette_records = cassette_store.load_cassette_records(run_id)
    if cassette_records is not None:
        return sorted(cassette_records, key=lambda record: record.sequence)
    return await _load_from_d1_previews(run_id)


async def _load_from_d1_previews(run_id: str) -> list[TraceRecord]:
    """Reconstruct a trace from the flight recorder's D1 row previews (fallback).

    Args:
        run_id: UUID of the run.

    Returns:
        The run's steps rebuilt from ``GET /runs/{run_id}``'s ``trace`` rows,
        ordered by sequence. Input/output are the truncated D1 previews.
    """
    async with httpx.AsyncClient(timeout=_LOAD_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{_flight_url()}/runs/{run_id}")
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    rows: list[dict[str, Any]] = body.get("trace", [])
    records = [_row_to_record(row) for row in rows]
    return sorted(records, key=lambda record: record.sequence)
