"""xqdrant similarity search for incidents and runbooks.

xqdrant (a Qdrant fork) runs at ``localhost:6333`` and is **internal only** — only
this backend talks to it (root ``CLAUDE.md`` §0/§10). A query string is embedded
with the BGE model via :mod:`cf_ai_client`, the vector is searched against a
collection, and each hit is returned as a :class:`trace_core.SearchResult`.

Two behaviours the schema and root ``CLAUDE.md`` require:

* **Threshold filtering** — only hits scoring above a per-collection relevance
  floor (:func:`config.similarity_threshold`) are returned; xqdrant returns weak
  matches too (root CLAUDE.md §10). Incidents use 0.75; runbooks use a lower floor
  (0.60) because incident→runbook cosine is structurally lower than
  incident→incident on the seeded BGE-768 data.
* **Attribution is always populated** — xqdrant's differentiator. When the search
  response carries ``score_explanation.top_dimensions``, those map into
  :attr:`~trace_core.Attribution.dims`; a stored ``payload.attribution`` block is
  used as fallback; otherwise only ``confidence_margin`` is synthesised as the
  score gap to the next-best hit.

The search call and embedding are module-level so tests monkeypatch them and never
touch a real server or the network.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from trace_core import (
    MAX_RETRIEVAL_RESULTS,
    Attribution,
    SearchResult,
)

from . import cf_ai_client, langfuse_client
from .config import similarity_threshold, xqdrant_url
from .dimension_label_map import enrich_attribution

_TEXT_KEYS = ("text", "description", "summary", "body")
XQDRANT_SEARCH_TIMEOUT_SECONDS = 15.0
"""Per-search timeout for the internal xqdrant HTTP API."""


@dataclass(frozen=True)
class _SearchHit:
    """One ranked hit from an XQdrant ``/points/search`` response."""

    id: str
    score: float
    payload: dict[str, object]
    score_explanation: dict[str, object] | None = None


def _hit_text(payload: dict[str, object]) -> str:
    """Pull the document text out of a hit payload, trying common field names."""
    for key in _TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _dims_from_explanation(score_explanation: dict[str, object] | None) -> dict[str, float]:
    """Map XQdrant ``score_explanation.top_dimensions`` into ``Attribution.dims``."""
    if not score_explanation:
        return {}
    top = score_explanation.get("top_dimensions")
    if not isinstance(top, list):
        return {}
    dims: dict[str, float] = {}
    for item in top:
        if not isinstance(item, dict):
            continue
        dimension = item.get("dimension")
        contribution = item.get("contribution")
        if dimension is None or contribution is None:
            continue
        dims[str(dimension)] = float(contribution)
    return dims


def _build_attribution(hit: _SearchHit, margin: float) -> Attribution:
    """Build attribution from XQdrant score explanation, payload, or margin fallback.

    Args:
        hit: The search hit (score explanation + payload).
        margin: Score gap to the next-best hit (fallback ``confidence_margin``).

    Returns:
        An :class:`trace_core.Attribution` (never ``None`` — the schema requires it).
    """
    dims = _dims_from_explanation(hit.score_explanation)
    if dims:
        return enrich_attribution(Attribution(dims=dims, terms={}, confidence_margin=margin))
    raw = hit.payload.get("attribution")
    if isinstance(raw, dict):
        try:
            return enrich_attribution(Attribution.model_validate(raw))
        except ValueError:
            pass  # Malformed payload attribution → fall back to the synthesised one.
    return Attribution(dims={}, terms={}, confidence_margin=margin)


def _margin(hits: list[_SearchHit], index: int, floor: float) -> float:
    """Score gap from ``hits[index]`` to the next hit (or the relevance floor)."""
    if index + 1 < len(hits):
        return hits[index].score - hits[index + 1].score
    return hits[index].score - floor


async def _query_collection(
    collection: str,
    vector: list[float],
    limit: int,
) -> list[_SearchHit]:
    """POST ``/collections/{collection}/points/search`` with XQdrant explainability.

    Args:
        collection: xqdrant collection name.
        vector: Query embedding (768-dim BGE).
        limit: Maximum hits to retrieve before threshold filtering.

    Returns:
        Ranked hits from the search ``result`` array.
    """
    url = f"{xqdrant_url().rstrip('/')}/collections/{collection}/points/search"
    body = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "with_explanation": True,
    }
    async with httpx.AsyncClient(timeout=XQDRANT_SEARCH_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        raw_result = response.json().get("result", [])

    hits: list[_SearchHit] = []
    if not isinstance(raw_result, list):
        return hits
    for item in raw_result:
        if not isinstance(item, dict):
            continue
        point_id = item.get("id")
        score = item.get("score")
        if point_id is None or score is None:
            continue
        payload_raw = item.get("payload") or {}
        payload = payload_raw if isinstance(payload_raw, dict) else {}
        explanation_raw = item.get("score_explanation")
        explanation = explanation_raw if isinstance(explanation_raw, dict) else None
        hits.append(
            _SearchHit(
                id=str(point_id),
                score=float(score),
                payload=payload,
                score_explanation=explanation,
            )
        )
    return hits


async def search_similar(
    query_text: str,
    collection: str,
    k: int = MAX_RETRIEVAL_RESULTS,
    threshold: float | None = None,
    embedding: list[float] | None = None,
) -> list[SearchResult]:
    """Embed ``query_text`` and return the top relevant hits from ``collection``.

    Args:
        query_text: Free text to embed and search with (e.g. an incident summary).
        collection: xqdrant collection name (``incidents`` or ``runbooks``).
        k: Maximum number of hits to retrieve before threshold filtering.
        threshold: Cosine-similarity floor a hit must exceed. ``None`` resolves the
            per-collection default (:func:`config.similarity_threshold`) — runbooks
            use a lower floor than incidents because incident→runbook cosine is
            structurally lower than incident→incident.
        embedding: Optional precomputed query vector. When provided the embed call
            is skipped and reused (the analyzer embeds the incident once and searches
            both the incidents and runbooks collections with the same vector).

    Returns:
        Hits scoring above the relevance floor, each carrying an
        :class:`~trace_core.Attribution`, ordered by descending score.
    """
    floor = similarity_threshold(collection) if threshold is None else threshold
    span = langfuse_client.start_span(
        name="xqdrant-search", input={"query": query_text, "collection": collection}
    )
    try:
        if embedding is None:
            embedding = await cf_ai_embed_query(query_text)
        hits = await _query_collection(collection, embedding, k)
    except Exception as exc:
        # End the span even when the embed/search fails, so a failed run produces a
        # complete (error-tagged) observation instead of a dangling one in Langfuse.
        langfuse_client.end_observation(span, output={"error": repr(exc)})
        raise
    results: list[SearchResult] = []
    for index, hit in enumerate(hits):
        if hit.score <= floor:
            continue
        results.append(
            SearchResult(
                id=hit.id,
                text=_hit_text(hit.payload),
                score=hit.score,
                attribution=_build_attribution(hit, _margin(hits, index, floor)),
            )
        )
    langfuse_client.end_observation(
        span,
        output={
            "count": len(results),
            "top_score": results[0].score if results else None,
        },
    )
    return results


async def cf_ai_embed_query(query_text: str) -> list[float]:
    """Embed a single query string and return its 768-dim vector.

    Thin wrapper over :func:`cf_ai_client.cf_ai_embed` that unwraps the
    single-element batch, so callers (and the search path) deal in one vector.

    Args:
        query_text: The text to embed.

    Returns:
        The embedding vector for ``query_text``.
    """
    vectors = await cf_ai_client.cf_ai_embed([query_text])
    return vectors[0]
