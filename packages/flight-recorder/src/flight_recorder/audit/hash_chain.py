"""Tamper-evident, hash-chained HMAC audit records.

Every recorded step gets an audit record. Each record carries a ``payload_hash``
(SHA-256 of its canonical JSON) and an ``hmac`` (HMAC-SHA256 of that hash, signed
with ``AUDIT_HMAC_KEY``). Records form a chain: each ``prev_hash`` equals the
previous record's ``payload_hash``. Tampering with any field changes its hash,
breaks the chain, and invalidates the HMAC — see ``spec/mcp-audit-trail-proposal.md``.

Records are written to Cloudflare D1 *before* execution proceeds (write-ahead),
so the intent to call is logged even if the call or the process then dies.
"""

from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field
from trace_core import AUDIT_HMAC_ALGORITHM, StepKind, canonical_json, sha256_hex

from ..config import AUDIT_HMAC_KEY_ENV, GENESIS_PREV_HASH, TRACE_RECORDS_TABLE
from ..storage import d1_client

_PREVIEW_CHARS = 500
"""Length of the input/output previews stored in D1 for cheap listing."""


class AuditRecord(BaseModel):
    """A verifiable audit record: its canonical payload plus hash and signature.

    Used to re-verify a chain after the fact — :func:`verify_chain` recomputes
    ``payload_hash`` and the HMAC from ``payload`` and checks the links.
    """

    payload: dict[str, Any] = Field(description="Canonical payload that was hashed and signed.")
    payload_hash: str = Field(description="SHA-256 of the canonical payload, e.g. 'sha256:...'.")
    hmac: str = Field(description="HMAC-SHA256 of payload_hash, signed with AUDIT_HMAC_KEY.")


def _hmac_key() -> bytes:
    """Return the HMAC secret from the environment, encoded to bytes."""
    return os.environ[AUDIT_HMAC_KEY_ENV].encode("utf-8")


def build_payload(
    run_id: str,
    step_id: str,
    kind: StepKind,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    prev_hash: str,
    *,
    sequence: int = 0,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Assemble the canonical payload dict for one audit record.

    Args:
        run_id: UUID of the run.
        step_id: UUID of the step this record covers.
        kind: The boundary-event kind (``llm_call``, ``tool_call``, ...).
        input_data: Input payload of the step.
        output_data: Output payload of the step.
        prev_hash: ``payload_hash`` of the previous record (or genesis).
        sequence: 0-based position of the step within the run.
        timestamp: ISO-8601 UTC time; defaults to "now" when omitted.

    Returns:
        The payload dict (canonicalised by :func:`compute_payload_hash`).
    """
    return {
        "run_id": run_id,
        "step_id": step_id,
        "sequence": sequence,
        "kind": kind,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "input": input_data,
        "output": output_data,
        "prev_hash": prev_hash,
    }


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Return the prefixed SHA-256 of a payload's canonical JSON."""
    return sha256_hex(canonical_json(payload))


def sign(payload_hash: str) -> str:
    """HMAC-SHA256 sign a payload hash with the configured secret.

    Args:
        payload_hash: The value returned by :func:`compute_payload_hash`.

    Returns:
        The HMAC hex digest.
    """
    return hmac.new(_hmac_key(), payload_hash.encode("utf-8"), sha256).hexdigest()


def _preview(data: dict[str, Any]) -> str:
    """First :data:`_PREVIEW_CHARS` chars of canonical JSON, for D1 listing."""
    return canonical_json(data)[:_PREVIEW_CHARS]


def write_audit_record(
    run_id: str,
    step_id: str,
    kind: StepKind,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    prev_hash: str,
    *,
    sequence: int = 0,
    input_preview: str | None = None,
    output_preview: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Build, sign, and write-ahead one audit record to Cloudflare D1.

    The record is written to ``trace_records`` before the caller proceeds, so the
    audit trail reflects intent even if the subsequent step fails.

    Only ``input_data``/``output_data`` (and the other payload fields) are hashed.
    ``input_preview``/``output_preview``/``metadata`` are display-only listing
    columns, so callers may pass human-readable summaries without affecting the
    hash chain; when omitted they default to canonical-JSON previews.

    Args:
        run_id: UUID of the run.
        step_id: UUID of the step this record covers.
        kind: The boundary-event kind.
        input_data: Input payload of the step.
        output_data: Output payload of the step.
        prev_hash: ``payload_hash`` of the previous record (use
            :data:`~flight_recorder.config.GENESIS_PREV_HASH` for the first).
        sequence: 0-based position of the step within the run.
        input_preview: Optional human-readable input summary for listing.
        output_preview: Optional human-readable output summary for listing.
        metadata: Optional extra metadata (e.g. ``operation``/``model_id``) merged
            into ``metadata_json`` alongside the hmac algorithm.

    Returns:
        This record's ``payload_hash`` — pass it as the next record's ``prev_hash``.
    """
    payload = build_payload(
        run_id, step_id, kind, input_data, output_data, prev_hash, sequence=sequence
    )
    payload_hash = compute_payload_hash(payload)
    signature = sign(payload_hash)
    record = {
        "id": step_id,
        "run_id": run_id,
        "sequence": sequence,
        "kind": kind,
        "timestamp_utc": payload["timestamp"],
        "payload_hash": payload_hash,
        "prev_hash": prev_hash,
        "hmac": signature,
        "input_preview": input_preview if input_preview is not None else _preview(input_data),
        "output_preview": (
            output_preview if output_preview is not None else _preview(output_data)
        ),
        "metadata_json": canonical_json(
            {"hmac_algorithm": AUDIT_HMAC_ALGORITHM, **(metadata or {})}
        ),
    }
    d1_client.insert(TRACE_RECORDS_TABLE, record)
    return payload_hash


def verify_record(record: AuditRecord) -> bool:
    """Return ``True`` if a single record's hash and HMAC are self-consistent.

    Recomputes the payload hash and HMAC from ``record.payload`` and compares
    them (constant-time for the HMAC) to the stored values.
    """
    expected_hash = compute_payload_hash(record.payload)
    if not hmac.compare_digest(expected_hash, record.payload_hash):
        return False
    return hmac.compare_digest(sign(expected_hash), record.hmac)


def verify_chain(records: list[AuditRecord]) -> bool:
    """Verify an ordered audit chain end to end.

    Checks that every record is self-consistent (:func:`verify_record`) and that
    each ``prev_hash`` links to the previous record's ``payload_hash``, starting
    from the genesis hash. Any tampering breaks one of these checks.

    Args:
        records: The chain in recorded order.

    Returns:
        ``True`` if the whole chain validates, else ``False``.
    """
    prev_hash = GENESIS_PREV_HASH
    for record in records:
        if record.payload.get("prev_hash") != prev_hash:
            return False
        if not verify_record(record):
            return False
        prev_hash = record.payload_hash
    return True
