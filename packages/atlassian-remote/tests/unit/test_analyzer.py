"""Analyzer orchestration tests — every collaborator is monkeypatched."""

from __future__ import annotations

from typing import Any

import pytest
from atlassian_remote import analyzer, duplicate_resolver, rca_generator, vector_search
from atlassian_remote.atlassian_client import AtlassianClient
from trace_core import Attribution, DuplicateVerdict, RcaDraft, SearchResult

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


async def test_analyze_incident_orchestrates_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch → search incidents + runbooks → draft → flag, all wired correctly."""

    async def fake_get_issue(_self: AtlassianClient, _key: str) -> dict[str, Any]:
        return _ISSUE

    monkeypatch.setattr(AtlassianClient, "get_issue", fake_get_issue)

    async def fake_search(_query: str, collection: str, k: int = 5) -> list[SearchResult]:
        return [_hit()] if collection == "incidents" else []

    monkeypatch.setattr(vector_search, "search_similar", fake_search)

    async def fake_generate(
        _text: str, _similar: list[SearchResult], _runbooks: list[SearchResult]
    ) -> RcaDraft:
        return _draft(0.5)  # below threshold → should flag for human

    monkeypatch.setattr(rca_generator, "generate_rca", fake_generate)

    result = await analyzer.analyze_incident("AO-1", "acc-123")

    assert result.rca_draft.proposed_severity == "high"
    assert [s.id for s in result.similar] == ["INC-1"]
    assert result.runbooks == []
    assert result.flag_for_human is True


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
