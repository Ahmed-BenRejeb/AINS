"""xqdrant search tests — embedding and the search call are monkeypatched."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from atlassian_remote import cf_ai_client, dimension_label_map, langfuse_client, vector_search
from trace_core import VECTOR_SIMILARITY_THRESHOLD


@pytest.fixture(autouse=True)
def _label_map_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire a minimal dimension label map for explainability tests."""
    path = tmp_path / "dimension_labels.json"
    path.write_text(
        json.dumps({"Security incident": [421], "DNS resolution failure": [88]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DIMENSION_LABELS_PATH", str(path))
    dimension_label_map.clear_dimension_label_cache()
    yield
    dimension_label_map.clear_dimension_label_cache()


def _hit(
    point_id: str,
    score: float,
    payload: dict[str, Any] | None = None,
    *,
    score_explanation: dict[str, Any] | None = None,
) -> vector_search._SearchHit:
    """Build a realistic XQdrant search hit for the fake query."""
    return vector_search._SearchHit(
        id=point_id,
        score=score,
        payload=payload or {},
        score_explanation=score_explanation,
    )


@pytest.fixture
def fake_search(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return an installer that wires a fixed set of hits into vector_search."""

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]

    monkeypatch.setattr(cf_ai_client, "cf_ai_embed", fake_embed)

    def _install(hits: list[vector_search._SearchHit]) -> None:
        async def fake_query(
            _collection: str, _vector: list[float], _limit: int
        ) -> list[vector_search._SearchHit]:
            return hits

        monkeypatch.setattr(vector_search, "_query_collection", fake_query)

    return _install


async def test_filters_hits_below_threshold(fake_search: Any) -> None:
    """Only hits scoring above VECTOR_SIMILARITY_THRESHOLD are returned."""
    fake_search(
        [
            _hit("a", 0.92, {"text": "strong match"}),
            _hit("b", 0.50, {"text": "weak match"}),  # below 0.75 → dropped
        ]
    )

    results = await vector_search.search_similar("query", "incidents", k=5)

    assert [r.id for r in results] == ["a"]
    assert results[0].text == "strong match"


async def test_confidence_margin_is_gap_to_next_hit(fake_search: Any) -> None:
    """Synthesised attribution margin is the score gap to the next-best hit."""
    fake_search([_hit("a", 0.90, {"text": "x"}), _hit("b", 0.80, {"text": "y"})])

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.confidence_margin == pytest.approx(0.10)
    # Last retained hit: margin measured to the relevance floor.
    assert results[1].attribution.confidence_margin == pytest.approx(
        0.80 - VECTOR_SIMILARITY_THRESHOLD
    )


async def test_maps_score_explanation_to_dims(fake_search: Any) -> None:
    """XQdrant ``score_explanation.top_dimensions`` maps into ``Attribution.dims``."""
    fake_search(
        [
            _hit(
                "a",
                0.95,
                {"text": "x"},
                score_explanation={
                    "top_dimensions": [
                        {"dimension": 421, "contribution": 0.145098},
                        {"dimension": 88, "contribution": 0.112},
                    ]
                },
            )
        ]
    )

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.dims == {"421": 0.145098, "88": 0.112}
    assert results[0].attribution.terms == {
        "Security incident": pytest.approx(0.145098),
        "DNS resolution failure": pytest.approx(0.112),
    }


async def test_score_explanation_takes_priority_over_payload_attribution(
    fake_search: Any,
) -> None:
    """Live XQdrant explainability wins over a stale payload attribution block."""
    fake_search(
        [
            _hit(
                "a",
                0.95,
                {
                    "text": "x",
                    "attribution": {
                        "dims": {"d0": 0.5},
                        "terms": {"timeout": 0.4},
                        "confidence_margin": 0.33,
                    },
                },
                score_explanation={
                    "top_dimensions": [{"dimension": 421, "contribution": 0.2}]
                },
            )
        ]
    )

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.dims == {"421": 0.2}
    assert results[0].attribution.terms == {"Security incident": pytest.approx(0.2)}


async def test_uses_payload_attribution_when_present(fake_search: Any) -> None:
    """A well-formed attribution block in the payload is used when no explanation."""
    fake_search(
        [
            _hit(
                "a",
                0.95,
                {
                    "text": "x",
                    "attribution": {
                        "dims": {"d0": 0.5},
                        "terms": {"timeout": 0.4},
                        "confidence_margin": 0.33,
                    },
                },
            )
        ]
    )

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.confidence_margin == 0.33
    assert results[0].attribution.dims == {"d0": 0.5}
    assert results[0].attribution.terms == {"timeout": 0.4}


async def test_falls_back_for_malformed_payload_attribution(fake_search: Any) -> None:
    """A malformed attribution payload is ignored in favour of the synthesised one."""
    fake_search([_hit("a", 0.95, {"text": "x", "attribution": {"bad": "shape"}})])

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.dims == {}
    assert results[0].attribution.terms == {}


async def test_empty_results_when_nothing_relevant(fake_search: Any) -> None:
    """All weak hits → an empty list (drives knowledge-gap detection upstream)."""
    fake_search([_hit("a", 0.40, {"text": "x"}), _hit("b", 0.20, {"text": "y"})])

    assert await vector_search.search_similar("query", "runbooks") == []


async def test_runbooks_use_lower_threshold_than_incidents(fake_search: Any) -> None:
    """A 0.65 hit is dropped for incidents (floor 0.75) but kept for runbooks (0.60).

    Regression for the runbooks-always-0 bug: incident→runbook cosine tops ~0.71 on
    the seeded data, so the strict incident floor silently dropped every runbook.
    The runbooks collection now uses a lower, separately-tuned relevance floor.
    """
    fake_search([_hit("rb", 0.65, {"text": "Runbook: DB Connection Pool Exhaustion"})])

    assert await vector_search.search_similar("query", "incidents") == []

    runbook_hits = await vector_search.search_similar("query", "runbooks")
    assert [r.id for r in runbook_hits] == ["rb"]


async def test_explicit_threshold_overrides_per_collection_default(fake_search: Any) -> None:
    """An explicit ``threshold`` argument wins over the per-collection default."""
    fake_search([_hit("a", 0.65, {"text": "x"})])

    # Incidents default to 0.75 → empty; an explicit 0.50 floor keeps the 0.65 hit.
    assert await vector_search.search_similar("query", "incidents", threshold=0.50)


async def test_span_is_ended_when_embed_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing embed still ends the Langfuse span (no dangling/orphan observation).

    Regression: the span was started before the embed call, so when embed raised
    (the live CF quota 429) the span was never ended → an incomplete trace.
    """
    ended: list[tuple[object, dict[str, object]]] = []

    async def boom(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("CF embed 429")

    monkeypatch.setattr(cf_ai_client, "cf_ai_embed", boom)
    monkeypatch.setattr(langfuse_client, "start_span", lambda **_kw: object())
    monkeypatch.setattr(
        langfuse_client,
        "end_observation",
        lambda span, output: ended.append((span, output)),
    )

    with pytest.raises(RuntimeError):
        await vector_search.search_similar("query", "incidents")

    assert len(ended) == 1  # span ended exactly once, on the failure path
    assert "error" in ended[0][1]
