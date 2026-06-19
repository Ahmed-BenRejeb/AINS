"""xqdrant similarity search for incidents and runbooks.

xqdrant (a Qdrant fork) runs at ``localhost:6333`` and is **internal only** — only
this backend talks to it (root ``CLAUDE.md`` §0/§10). A query string is embedded
with the BGE model via :mod:`cf_ai_client`, the vector is searched against a
collection, and each hit is returned as a :class:`trace_core.SearchResult`.

Two behaviours the schema and root ``CLAUDE.md`` require:

* **Threshold filtering** — only hits with ``score > VECTOR_SIMILARITY_THRESHOLD``
  (0.75) are returned; xqdrant returns weak matches too (root CLAUDE.md §10).
* **Attribution is always populated** — xqdrant's differentiator. When the payload
  carries an explainability block it is used verbatim; otherwise a fallback
  :class:`trace_core.Attribution` is synthesised with the ``confidence_margin``
  computed as the score gap to the next-best hit.

The qdrant client and embedding call are module-level so tests monkeypatch them
and never touch a real server or the network.
"""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http.models import ScoredPoint
from trace_core import (
    MAX_RETRIEVAL_RESULTS,
    VECTOR_SIMILARITY_THRESHOLD,
    Attribution,
    SearchResult,
)

from . import cf_ai_client
from .config import xqdrant_url

_TEXT_KEYS = ("text", "description", "summary", "body")


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    """Build (and cache) the xqdrant client pointed at ``XQDRANT_URL``."""
    return QdrantClient(url=xqdrant_url())


def _hit_text(payload: dict[str, object]) -> str:
    """Pull the document text out of a hit payload, trying common field names."""
    for key in _TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _build_attribution(payload: dict[str, object], margin: float) -> Attribution:
    """Use the payload's explainability block if present, else synthesise one.

    Args:
        payload: The hit payload from xqdrant.
        margin: Score gap to the next-best hit (fallback ``confidence_margin``).

    Returns:
        An :class:`trace_core.Attribution` (never ``None`` — the schema requires it).
    """
    raw = payload.get("attribution")
    if isinstance(raw, dict):
        try:
            return Attribution.model_validate(raw)
        except ValueError:
            pass  # Malformed payload attribution → fall back to the synthesised one.
    return Attribution(dims={}, terms={}, confidence_margin=margin)


def _margin(points: list[ScoredPoint], index: int) -> float:
    """Score gap from ``points[index]`` to the next hit (or the relevance floor)."""
    if index + 1 < len(points):
        return points[index].score - points[index + 1].score
    return points[index].score - VECTOR_SIMILARITY_THRESHOLD


async def search_similar(
    query_text: str,
    collection: str,
    k: int = MAX_RETRIEVAL_RESULTS,
) -> list[SearchResult]:
    """Embed ``query_text`` and return the top relevant hits from ``collection``.

    Args:
        query_text: Free text to embed and search with (e.g. an incident summary).
        collection: xqdrant collection name (``incidents`` or ``runbooks``).
        k: Maximum number of hits to retrieve before threshold filtering.

    Returns:
        Hits with ``score > VECTOR_SIMILARITY_THRESHOLD``, each carrying an
        :class:`~trace_core.Attribution`, ordered by descending score.
    """
    embedding = await cf_ai_embed_query(query_text)
    response = get_client().query_points(
        collection_name=collection,
        query=embedding,
        limit=k,
        with_payload=True,
    )
    points: list[ScoredPoint] = response.points
    results: list[SearchResult] = []
    for index, point in enumerate(points):
        if point.score <= VECTOR_SIMILARITY_THRESHOLD:
            continue
        payload = point.payload or {}
        results.append(
            SearchResult(
                id=str(point.id),
                text=_hit_text(payload),
                score=point.score,
                attribution=_build_attribution(payload, _margin(points, index)),
            )
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
