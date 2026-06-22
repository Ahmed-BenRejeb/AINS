"""Analyzer orchestration tests — every collaborator is monkeypatched."""

from __future__ import annotations

from typing import Any

import pytest
from atlassian_remote import (
    analyzer,
    duplicate_resolver,
    eval_client,
    rca_generator,
    recording,
    vector_search,
)
from atlassian_remote.atlassian_client import AtlassianClient
from trace_core import (
    Attribution,
    DuplicateVerdict,
    EvalVerdict,
    RcaDraft,
    SearchResult,
    SelfEvaluation,
)

_ISSUE = {
    "key": "AO-1",
    "fields": {
        "summary": "DB outage",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "connection pool exhausted"}],
                }
            ],
        },
    },
}


def _draft(confidence: float) -> RcaDraft:
    return RcaDraft(
        root_cause_hypothesis="pool exhausted",
        evidence=[],
        severity_rationale="impact",
        proposed_severity="high",
        proposed_assignee_team="platform",
        duplicate_check=[],
        knowledge_gaps=[],
        confidence_score=confidence,
    )


def _hit() -> SearchResult:
    return SearchResult(
        id="INC-1",
        text="db pool",
        score=0.9,
        attribution=Attribution(dims={}, terms={}, confidence_margin=0.1),
    )


def test_extract_incident_text_flattens_adf_description() -> None:
    """Summary and the flattened ADF description are both present."""
    text = analyzer.extract_incident_text(_ISSUE)

    assert "DB outage" in text
    assert "connection pool exhausted" in text


def test_extract_incident_text_handles_string_description() -> None:
    """A plain-string description (API v2 shape) is handled too."""
    issue = {"fields": {"summary": "S", "description": "raw text body"}}

    assert "raw text body" in analyzer.extract_incident_text(issue)


def _verdict(run_id: str) -> EvalVerdict:
    return EvalVerdict(
        run_id=run_id,
        trial_number=0,
        verdict="pass",
        dimensions={},
        self_evaluation=SelfEvaluation(
            judge_confidence=0.9, self_critique="ok", flag_for_human=False
        ),
        replay_link=f"https://flight.ahmedxsaad.me/runs/{run_id}",
        recommended_action="No action.",
    )


async def test_analyze_incident_orchestrates_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch → record → search + draft → manifest → eval → envelope, all wired."""

    async def fake_get_issue(_self: AtlassianClient, _key: str) -> dict[str, Any]:
        return _ISSUE

    monkeypatch.setattr(AtlassianClient, "get_issue", fake_get_issue)

    async def fake_embed(_text: str) -> list[float]:
        return [0.1] * 8

    monkeypatch.setattr(vector_search, "cf_ai_embed_query", fake_embed)

    async def fake_search(
        _query: str, collection: str, k: int = 5, embedding: list[float] | None = None
    ) -> list[SearchResult]:
        return [_hit()] if collection == "incidents" else []

    monkeypatch.setattr(vector_search, "search_similar", fake_search)

    # Capture the tool-call records the analyzer tapes for each retrieval.
    tool_calls: list[str] = []
    monkeypatch.setattr(
        recording.RunRecorder,
        "record_tool_call",
        lambda _self, **kw: tool_calls.append(str(kw.get("arguments", {}).get("collection"))),
    )

    async def fake_generate(
        _text: str, _similar: list[SearchResult], _runbooks: list[SearchResult]
    ) -> RcaDraft:
        return _draft(0.5)  # below threshold → should flag for human

    monkeypatch.setattr(rca_generator, "generate_rca", fake_generate)

    # Pin the run id and stub the flight-recorder + eval-engine seams (no network).
    monkeypatch.setattr(recording, "new_run_id", lambda: "run-test-123")
    manifests: list[dict[str, Any]] = []

    def fake_persist(run_id: str, **kwargs: Any) -> None:
        manifests.append({"run_id": run_id, **kwargs})

    monkeypatch.setattr(recording, "persist_manifest", fake_persist)

    async def fake_eval(run_id: str) -> EvalVerdict:
        return _verdict(run_id)

    monkeypatch.setattr(eval_client, "request_evaluation", fake_eval)

    result = await analyzer.analyze_incident("AO-1", "acc-123")

    assert result.run_id == "run-test-123"
    assert result.rca_draft.proposed_severity == "high"
    assert [s.id for s in result.similar] == ["INC-1"]
    assert result.runbooks == []
    assert result.flag_for_human is True
    # The manifest was persisted for the incident, and the eval verdict came back.
    assert manifests and manifests[0]["task_id"] == "AO-1"
    assert result.eval_verdict is not None
    assert result.eval_verdict.verdict == "pass"
    assert result.replay_link == "https://dashboard.ahmedxsaad.me/replay/run-test-123"
    # Both retrievals were taped as tool_call steps (incidents + runbooks).
    assert tool_calls == ["incidents", "runbooks"]


async def test_resolve_incident_duplicate_orchestrates_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch → search incidents → judge duplicate → flag, all wired correctly."""

    async def fake_get_issue(_self: AtlassianClient, _key: str) -> dict[str, Any]:
        return _ISSUE

    monkeypatch.setattr(AtlassianClient, "get_issue", fake_get_issue)

    async def fake_search(_query: str, collection: str, k: int = 5) -> list[SearchResult]:
        return [_hit()] if collection == "incidents" else []

    monkeypatch.setattr(vector_search, "search_similar", fake_search)

    async def fake_resolve(_text: str, _similar: list[SearchResult]) -> DuplicateVerdict:
        return DuplicateVerdict(
            is_duplicate=True,
            duplicate_of="INC-1",
            confidence=0.92,
            rationale="same root cause",
            explanation="Looks like a duplicate of INC-1.",
            candidates=[],
        )

    monkeypatch.setattr(duplicate_resolver, "resolve_duplicate", fake_resolve)

    result = await analyzer.resolve_incident_duplicate("AO-1", "acc-123")

    assert result.verdict.is_duplicate is True
    assert result.verdict.duplicate_of == "INC-1"
    assert [s.id for s in result.similar] == ["INC-1"]
    assert result.flag_for_human is False  # confident → safe to auto-link
