"""RCA generator tests — the CF Workers AI chat call is monkeypatched."""

from __future__ import annotations

import json
from typing import Any

import pytest
from atlassian_remote import cf_ai_client, rca_generator
from trace_core import Attribution, RcaDraft, SearchResult


def _hit(point_id: str, text: str, score: float = 0.9) -> SearchResult:
    return SearchResult(
        id=point_id,
        text=text,
        score=score,
        attribution=Attribution(dims={}, terms={}, confidence_margin=0.1),
    )


def _rca_payload(confidence: float = 0.9) -> dict[str, Any]:
    return {
        "root_cause_hypothesis": "DB connection pool exhausted",
        "evidence": ["INC-1: identical pool timeout"],
        "severity_rationale": "customer-facing outage",
        "proposed_severity": "high",
        "proposed_assignee_team": "platform",
        "duplicate_check": ["INC-1"],
        "knowledge_gaps": [],
        "confidence_score": confidence,
    }


@pytest.fixture
def mock_chat(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return an installer that makes cf_ai_chat return a fixed raw string."""

    def _install(raw: str) -> None:
        async def fake_chat(messages: Any, model: Any = None, max_tokens: int = 1024) -> str:
            return raw

        monkeypatch.setattr(cf_ai_client, "cf_ai_chat", fake_chat)

    return _install


async def test_generate_rca_parses_plain_json(mock_chat: Any) -> None:
    """A clean JSON response validates into an RcaDraft."""
    mock_chat(json.dumps(_rca_payload()))

    draft = await rca_generator.generate_rca("incident text", [_hit("INC-1", "pool")], [])

    assert isinstance(draft, RcaDraft)
    assert draft.proposed_severity == "high"
    assert draft.duplicate_check == ["INC-1"]


async def test_generate_rca_strips_code_fence(mock_chat: Any) -> None:
    """A ```json fenced response is unwrapped before validation."""
    mock_chat("```json\n" + json.dumps(_rca_payload()) + "\n```")

    draft = await rca_generator.generate_rca("incident", [], [])

    assert draft.root_cause_hypothesis == "DB connection pool exhausted"


async def test_generate_rca_tolerates_preamble(mock_chat: Any) -> None:
    """Surrounding prose is discarded by narrowing to the outermost braces."""
    mock_chat("Here is the analysis: " + json.dumps(_rca_payload()) + " Hope it helps.")

    draft = await rca_generator.generate_rca("incident", [], [])

    assert draft.confidence_score == 0.9


def test_needs_human_review_uses_confidence_threshold() -> None:
    """Below CONFIDENCE_THRESHOLD (0.70) flags for human review; at/above does not."""
    low = RcaDraft.model_validate(_rca_payload(0.50))
    high = RcaDraft.model_validate(_rca_payload(0.85))

    assert rca_generator.needs_human_review(low) is True
    assert rca_generator.needs_human_review(high) is False


def test_prompt_embeds_evidence_and_marks_empty_blocks() -> None:
    """The prompt cites retrieved ids and signals when a block is empty."""
    prompt = rca_generator.build_rca_prompt("OUTAGE TEXT", [_hit("INC-7", "timeout")], [])

    assert "INC-7" in prompt
    assert "OUTAGE TEXT" in prompt
    assert "none retrieved" in prompt  # empty runbooks block
