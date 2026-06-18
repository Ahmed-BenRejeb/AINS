"""Tests for the hash-chained HMAC audit trail."""

from __future__ import annotations

from typing import Any

from flight_recorder.audit import hash_chain
from flight_recorder.audit.hash_chain import AuditRecord
from flight_recorder.config import GENESIS_PREV_HASH


def _make_record(
    step_id: str,
    prev_hash: str,
    *,
    sequence: int,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
) -> AuditRecord:
    payload = hash_chain.build_payload(
        run_id="run-1",
        step_id=step_id,
        kind="llm_call",
        input_data=input_data,
        output_data=output_data,
        prev_hash=prev_hash,
        sequence=sequence,
        timestamp="2026-06-18T00:00:00+00:00",
    )
    payload_hash = hash_chain.compute_payload_hash(payload)
    return AuditRecord(
        payload=payload, payload_hash=payload_hash, hmac=hash_chain.sign(payload_hash)
    )


def _build_chain() -> list[AuditRecord]:
    first = _make_record(
        "s0", GENESIS_PREV_HASH, sequence=0, input_data={"q": 1}, output_data={"a": 1}
    )
    second = _make_record(
        "s1", first.payload_hash, sequence=1, input_data={"q": 2}, output_data={"a": 2}
    )
    return [first, second]


def test_valid_chain_verifies() -> None:
    """A well-formed chain validates end to end."""
    assert hash_chain.verify_chain(_build_chain()) is True


def test_tampered_payload_breaks_chain() -> None:
    """Mutating a recorded field invalidates that record's hash."""
    chain = _build_chain()
    chain[0].payload["output"] = {"a": 999}  # tamper after signing
    assert hash_chain.verify_chain(chain) is False


def test_tampered_hmac_is_detected() -> None:
    """A forged signature is rejected even if the hash still matches."""
    chain = _build_chain()
    chain[1].hmac = "0" * 64
    assert hash_chain.verify_chain(chain) is False


def test_broken_link_is_detected() -> None:
    """A prev_hash that does not point at the previous record breaks the chain."""
    chain = _build_chain()
    chain[1].payload["prev_hash"] = GENESIS_PREV_HASH  # should point at chain[0]
    # Re-sign so the record is internally consistent; only the link is wrong.
    chain[1].payload_hash = hash_chain.compute_payload_hash(chain[1].payload)
    chain[1].hmac = hash_chain.sign(chain[1].payload_hash)
    assert hash_chain.verify_chain(chain) is False


def test_write_audit_record_chains_and_persists(
    captured_d1: list[tuple[str, dict[str, Any]]],
) -> None:
    """write_audit_record returns the next prev_hash and write-aheads to D1."""
    first_hash = hash_chain.write_audit_record(
        run_id="run-1",
        step_id="s0",
        kind="llm_call",
        input_data={"q": 1},
        output_data={"a": 1},
        prev_hash=GENESIS_PREV_HASH,
        sequence=0,
    )
    second_hash = hash_chain.write_audit_record(
        run_id="run-1",
        step_id="s1",
        kind="tool_call",
        input_data={"q": 2},
        output_data={"a": 2},
        prev_hash=first_hash,
        sequence=1,
    )

    assert first_hash.startswith("sha256:")
    assert second_hash != first_hash
    assert [table for table, _ in captured_d1] == ["trace_records", "trace_records"]
    assert captured_d1[1][1]["prev_hash"] == first_hash
