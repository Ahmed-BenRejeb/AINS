"""xqdrant search tests — embedding and the qdrant client are monkeypatched."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from atlassian_remote import cf_ai_client, vector_search
from qdrant_client.http.models import QueryResponse, ScoredPoint
from trace_core import VECTOR_SIMILARITY_THRESHOLD


def _point(point_id: str, score: float, payload: dict[str, Any] | None = None) -> ScoredPoint:
    """Build a realistic xqdrant ScoredPoint for the fake client."""
    return ScoredPoint(id=point_id, version=0, score=score, payload=payload)


@pytest.fixture
def fake_search(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return an installer that wires a fixed set of hits into vector_search."""

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]

    monkeypatch.setattr(cf_ai_client, "cf_ai_embed", fake_embed)

    def _install(points: list[ScoredPoint]) -> None:
        client = SimpleNamespace(query_points=lambda **_kwargs: QueryResponse(points=points))
        monkeypatch.setattr(vector_search, "get_client", lambda: client)

    return _install


async def test_filters_hits_below_threshold(fake_search: Any) -> None:
    """Only hits scoring above VECTOR_SIMILARITY_THRESHOLD are returned."""
    fake_search(
        [
            _point("a", 0.92, {"text": "strong match"}),
            _point("b", 0.50, {"text": "weak match"}),  # below 0.75 → dropped
        ]
    )

    results = await vector_search.search_similar("query", "incidents", k=5)

    assert [r.id for r in results] == ["a"]
    assert results[0].text == "strong match"


async def test_confidence_margin_is_gap_to_next_hit(fake_search: Any) -> None:
    """Synthesised attribution margin is the score gap to the next-best hit."""
    fake_search([_point("a", 0.90, {"text": "x"}), _point("b", 0.80, {"text": "y"})])

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.confidence_margin == pytest.approx(0.10)
    # Last retained hit: margin measured to the relevance floor.
    assert results[1].attribution.confidence_margin == pytest.approx(
        0.80 - VECTOR_SIMILARITY_THRESHOLD
    )


async def test_uses_payload_attribution_when_present(fake_search: Any) -> None:
    """A well-formed attribution block in the payload is used verbatim."""
    fake_search(
        [
            _point(
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
    fake_search([_point("a", 0.95, {"text": "x", "attribution": {"bad": "shape"}})])

    results = await vector_search.search_similar("query", "incidents")

    assert results[0].attribution.dims == {}
    assert results[0].attribution.terms == {}


async def test_empty_results_when_nothing_relevant(fake_search: Any) -> None:
    """All weak hits → an empty list (drives knowledge-gap detection upstream)."""
    fake_search([_point("a", 0.40, {"text": "x"}), _point("b", 0.20, {"text": "y"})])

    assert await vector_search.search_similar("query", "runbooks") == []
