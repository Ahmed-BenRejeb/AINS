"""Tests for the trace-core Pydantic models.

Covers two things:
  1. Every model instantiates and round-trips through JSON unchanged.
  2. An :class:`AuditBlock` hash chain built over real records validates, and
     tampering with any record breaks the chain (tamper-evidence).
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from trace_core import (
    Attribution,
    AuditBlock,
    DimensionScore,
    DriftReport,
    DuplicateVerdict,
    EvalVerdict,
    FailureAttribution,
    RcaDraft,
    RunManifest,
    SearchResult,
    SelfEvaluation,
    StepMetadata,
    TraceRecord,
    canonical_json,
    sha256_hex,
)

_TS = datetime(2026, 6, 18, 12, 0, 0, tzinfo=UTC)


# ─── Fixtures: one fully-populated instance of every model ─────────────────────


def _step_metadata() -> StepMetadata:
    return StepMetadata(
        model_id="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        tool_name=None,
        tool_version=None,
        latency_ms=812.5,
        sampling_params={"temperature": 0.0, "max_tokens": 1000},
    )


def _audit_block() -> AuditBlock:
    return AuditBlock(
        prev_hash="sha256:" + "0" * 64,
        payload_hash="sha256:abc123",
        hmac="sha256:def456",
    )


def _trace_record() -> TraceRecord:
    return TraceRecord(
        run_id="run-1",
        step_id="step-1",
        sequence=0,
        timestamp=_TS,
        kind="llm_call",
        input={"messages": [{"role": "user", "content": "hi"}]},
        output={"response": "hello"},
        metadata=_step_metadata(),
        audit=_audit_block(),
    )


def _run_manifest() -> RunManifest:
    return RunManifest(
        run_id="run-1",
        agent_id="incident-rca-agent",
        task_id="incident-AO-42",
        flight_mode="record",
        cassette_id="sentinel-cassettes/run-1",
        step_count=3,
        status="completed",
        started_at=_TS,
        completed_at=_TS,
    )


def _eval_verdict() -> EvalVerdict:
    return EvalVerdict(
        run_id="run-1",
        trial_number=0,
        verdict="fail",
        dimensions={
            "correctness": DimensionScore(score=0.4, reason="wrong severity", confidence=0.8),
            "efficiency": DimensionScore(score=0.9, reason="few steps", confidence=0.7),
        },
        failure_attribution=FailureAttribution(
            step=3,
            component="retrieval",
            description="irrelevant runbook retrieved",
            confidence=0.87,
        ),
        self_evaluation=SelfEvaluation(
            judge_confidence=0.73,
            self_critique="Attribution based on incomplete retrieval evidence.",
            flag_for_human=True,
        ),
        replay_link="https://flight.ahmedxsaad.me/replay/run-1",
        recommended_action="Open replay and bisect step 3.",
    )


def _search_result() -> SearchResult:
    return SearchResult(
        id="incident-AO-7",
        text="database connection refused",
        score=0.91,
        attribution=Attribution(
            dims={"0": 0.12, "1": 0.05},
            terms={"database": 0.4, "connection": 0.3},
            confidence_margin=0.08,
        ),
    )


def _rca_draft() -> RcaDraft:
    return RcaDraft(
        root_cause_hypothesis="Connection pool exhausted under load.",
        evidence=["incident-AO-7 had identical symptoms", "runbook RB-3 §2"],
        severity_rationale="Customer-facing outage, no workaround.",
        proposed_severity="high",
        proposed_assignee_team="platform-ops",
        duplicate_check=["incident-AO-7"],
        knowledge_gaps=[],
        confidence_score=0.82,
    )


def _duplicate_verdict() -> DuplicateVerdict:
    return DuplicateVerdict(
        is_duplicate=True,
        duplicate_of="incident-AO-7",
        confidence=0.9,
        rationale="Same connection-pool exhaustion described with different wording.",
        explanation="This looks like a duplicate of incident-AO-7; linking them.",
        candidates=["incident-AO-12"],
    )


def _drift_report() -> DriftReport:
    return DriftReport(
        baseline_run_count=8,
        current_run_count=8,
        pass_rate_baseline=0.875,
        pass_rate_current=0.5,
        pass_rate_delta=-0.375,
        mean_score_baseline=0.82,
        mean_score_current=0.61,
        dimension_deltas={"correctness": -0.3, "efficiency": -0.05},
        most_shifted_dimension="correctness",
        semantic_drift=0.22,
        drift_detected=True,
        drift_score=0.375,
        summary="Drift detected: pass rate 88% → 50% (-38%); largest dimension shift: "
        "correctness -0.30; output semantic drift 0.22.",
    )


_ALL_INSTANCES: list[BaseModel] = [
    _step_metadata(),
    _audit_block(),
    _trace_record(),
    _run_manifest(),
    DimensionScore(score=0.5, reason="partial", confidence=0.6),
    FailureAttribution(step=1, component="planning", description="loop", confidence=0.5),
    SelfEvaluation(judge_confidence=0.9, self_critique="solid", flag_for_human=False),
    _eval_verdict(),
    Attribution(dims={"0": 0.1}, terms={"x": 0.2}, confidence_margin=0.3),
    _search_result(),
    _rca_draft(),
    _duplicate_verdict(),
    _drift_report(),
]


# ─── Tests ─────────────────────────────────────────────────────────────────────


def test_every_model_round_trips_through_json() -> None:
    """Each model serializes to JSON and deserializes back to an equal instance."""
    for instance in _ALL_INSTANCES:
        dumped = instance.model_dump_json()
        restored = type(instance).model_validate_json(dumped)
        assert restored == instance, f"{type(instance).__name__} did not round-trip"


def test_optional_fields_default_to_none() -> None:
    """Optional fields can be omitted and default to None."""
    meta = StepMetadata()
    assert meta.model_id is None
    assert meta.tool_name is None
    assert meta.latency_ms is None
    manifest = _run_manifest().model_copy(update={"cassette_id": None, "completed_at": None})
    assert manifest.cassette_id is None
    assert manifest.completed_at is None


def test_duplicate_verdict_allows_null_target() -> None:
    """A non-duplicate verdict can omit duplicate_of (defaults to None)."""
    verdict = DuplicateVerdict(
        is_duplicate=False,
        confidence=0.2,
        rationale="Different root cause.",
        explanation="Not a duplicate.",
        candidates=[],
    )
    restored = DuplicateVerdict.model_validate_json(verdict.model_dump_json())
    assert restored.duplicate_of is None
    assert restored.is_duplicate is False


def test_drift_report_allows_null_semantic_drift() -> None:
    """semantic_drift is optional (None when no output text was supplied)."""
    report = _drift_report().model_copy(update={"semantic_drift": None})
    restored = DriftReport.model_validate_json(report.model_dump_json())
    assert restored.semantic_drift is None
    assert restored.drift_detected is True


def test_eval_verdict_passes_with_no_attribution() -> None:
    """A passing verdict needs no failure attribution."""
    verdict = _eval_verdict().model_copy(update={"verdict": "pass", "failure_attribution": None})
    restored = EvalVerdict.model_validate_json(verdict.model_dump_json())
    assert restored.failure_attribution is None
    assert restored.verdict == "pass"


# ─── Audit hash-chain validation ───────────────────────────────────────────────

_HMAC_KEY = b"test-audit-key"
_GENESIS = "sha256:" + "0" * 64


def _content_hash(record: TraceRecord) -> str:
    """Hash a record's content (everything except its own audit block)."""
    content: dict[str, Any] = record.model_dump(mode="json", exclude={"audit"})
    return sha256_hex(canonical_json(content))


def _sign(payload_hash: str) -> str:
    """HMAC-SHA256 a payload hash with the audit key."""
    mac = hmac.new(_HMAC_KEY, payload_hash.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256:{mac}"


def _build_chain(records: list[TraceRecord]) -> list[TraceRecord]:
    """Attach a valid hash-chained, HMAC-signed AuditBlock to each record."""
    chained: list[TraceRecord] = []
    prev_hash = _GENESIS
    for record in records:
        payload_hash = _content_hash(record)
        audit = AuditBlock(
            prev_hash=prev_hash,
            payload_hash=payload_hash,
            hmac=_sign(payload_hash),
        )
        chained.append(record.model_copy(update={"audit": audit}))
        prev_hash = payload_hash
    return chained


def _verify_chain(records: list[TraceRecord]) -> bool:
    """Recompute hashes + HMACs and confirm the chain is unbroken."""
    prev_hash = _GENESIS
    for record in records:
        if record.audit.prev_hash != prev_hash:
            return False
        if record.audit.payload_hash != _content_hash(record):
            return False
        if record.audit.hmac != _sign(record.audit.payload_hash):
            return False
        prev_hash = record.audit.payload_hash
    return True


def _sample_records() -> list[TraceRecord]:
    base = _trace_record()
    return [
        base.model_copy(update={"step_id": f"step-{i}", "sequence": i, "output": {"i": i}})
        for i in range(3)
    ]


def test_audit_chain_validates() -> None:
    """A correctly constructed audit chain verifies end to end."""
    chain = _build_chain(_sample_records())
    assert _verify_chain(chain) is True


def test_audit_chain_detects_payload_tampering() -> None:
    """Modifying a record's content breaks its payload_hash and the chain."""
    chain = _build_chain(_sample_records())
    chain[1] = chain[1].model_copy(update={"output": {"tampered": True}})
    assert _verify_chain(chain) is False


def test_audit_chain_detects_link_tampering() -> None:
    """Cutting a link (wrong prev_hash) breaks the chain."""
    chain = _build_chain(_sample_records())
    broken_audit = chain[2].audit.model_copy(update={"prev_hash": _GENESIS})
    chain[2] = chain[2].model_copy(update={"audit": broken_audit})
    assert _verify_chain(chain) is False
