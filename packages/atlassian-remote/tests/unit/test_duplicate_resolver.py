"""Duplicate resolver tests — the CF Workers AI chat call is monkeypatched."""

from __future__ import annotations

import json
from typing import Any

import pytest
from atlassian_remote import cf_ai_client, duplicate_resolver
from trace_core import Attribution, DuplicateVerdict, SearchResult


def _hit(point_id: str, text: str, score: float = 0.9) -> SearchResult:
    return SearchResult(
        id=point_id,
        text=text,
        score=score,
        attribution=Attribution(dims={}, terms={}, confidence_margin=0.1),
    )


def _verdict_payload(
    *, is_duplicate: bool = True, duplicate_of: str | None = "INC-1", confidence: float = 0.9
) -> dict[str, Any]:
    return {
        "is_duplicate": is_duplicate,
        "duplicate_of": duplicate_of,
        "confidence": confidence,
        "rationale": "same connection-pool exhaustion, different wording",
        "explanation": "Hi — this looks like a duplicate of INC-1; linking them.",
        "candidates": ["INC-2"],
    }


@pytest.fixture
def mock_chat(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return an installer that makes cf_ai_chat return a fixed raw string."""

    def _install(raw: str) -> None:
        async def fake_chat(messages: Any, model: Any = None, max_tokens: int = 1024) -> str:
            return raw

        monkeypatch.setattr(cf_ai_client, "cf_ai_chat", fake_chat)

    return _install


async def test_resolve_duplicate_parses_plain_json(mock_chat: Any) -> None:
    """A clean JSON response validates into a DuplicateVerdict."""
    mock_chat(json.dumps(_verdict_payload()))

    verdict = await duplicate_resolver.resolve_duplicate("incident text", [_hit("INC-1", "pool")])

    assert isinstance(verdict, DuplicateVerdict)
    assert verdict.is_duplicate is True
    assert verdict.duplicate_of == "INC-1"
    assert verdict.candidates == ["INC-2"]


async def test_resolve_duplicate_strips_code_fence(mock_chat: Any) -> None:
    """A ```json fenced response is unwrapped before validation (shared _extract_json)."""
    mock_chat("```json\n" + json.dumps(_verdict_payload()) + "\n```")

    verdict = await duplicate_resolver.resolve_duplicate("incident", [])

    assert verdict.duplicate_of == "INC-1"


async def test_resolve_duplicate_tolerates_preamble(mock_chat: Any) -> None:
    """Surrounding prose is discarded by narrowing to the outermost braces."""
    mock_chat("Here is the verdict: " + json.dumps(_verdict_payload()) + " Thanks.")

    verdict = await duplicate_resolver.resolve_duplicate("incident", [])

    assert verdict.confidence == 0.9


def test_needs_human_review_truth_table() -> None:
    """Auto-linking is only safe when confident AND a concrete duplicate is named."""
    confident = DuplicateVerdict.model_validate(_verdict_payload(confidence=0.9))
    low_conf = DuplicateVerdict.model_validate(_verdict_payload(confidence=0.5))
    not_dup = DuplicateVerdict.model_validate(
        _verdict_payload(is_duplicate=False, duplicate_of=None)
    )
    no_target = DuplicateVerdict.model_validate(_verdict_payload(duplicate_of=None))

    assert duplicate_resolver.needs_human_review(confident) is False
    assert duplicate_resolver.needs_human_review(low_conf) is True
    assert duplicate_resolver.needs_human_review(not_dup) is True
    assert duplicate_resolver.needs_human_review(no_target) is True


def test_prompt_embeds_evidence_and_marks_empty_blocks() -> None:
    """The prompt cites retrieved ids, the incident text, and signals an empty block."""
    with_hit = duplicate_resolver.build_duplicate_prompt("OUTAGE TEXT", [_hit("INC-7", "timeout")])
    empty = duplicate_resolver.build_duplicate_prompt("OUTAGE TEXT", [])

    assert "INC-7" in with_hit
    assert "OUTAGE TEXT" in with_hit
    assert "none retrieved" in empty
