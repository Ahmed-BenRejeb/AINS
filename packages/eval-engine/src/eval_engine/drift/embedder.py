"""Output-embedding helpers for semantic drift detection (UC1 §2.3).

The agents' output text for a window of runs is embedded with the BGE model (768-dim)
via Cloudflare Workers AI and averaged into a single centroid; the cosine distance
between the baseline and current centroids measures how much the *shape* of the
outputs has shifted (length, structure, topic) independently of the pass/fail verdict.

All embedding goes through :func:`eval_engine.cf_ai_client.cf_ai_embed`, which tests
monkeypatch, so this module makes no real network call under test.
"""

from __future__ import annotations

import math

from .. import cf_ai_client


def _centroid(vectors: list[list[float]]) -> list[float]:
    """Average a list of equal-length vectors into their centroid.

    Args:
        vectors: Non-empty list of equal-length embedding vectors.

    Returns:
        The element-wise mean vector.
    """
    count = len(vectors)
    dim = len(vectors[0])
    return [sum(vector[i] for vector in vectors) / count for i in range(dim)]


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance (``1 - cosine_similarity``) between two vectors, in [0, 2].

    Args:
        a: First vector.
        b: Second vector (same dimensionality as ``a``).

    Returns:
        ``0.0`` for identical direction, ``1.0`` for orthogonal, up to ``2.0`` for
        opposite. Returns ``0.0`` if either vector has zero magnitude.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return 1.0 - dot / (norm_a * norm_b)


async def embed_centroid(outputs: list[str]) -> list[float] | None:
    """Embed a window of output strings and return their centroid vector.

    Args:
        outputs: The agents' output texts for one window of runs.

    Returns:
        The centroid of the BGE embeddings, or ``None`` when ``outputs`` is empty or
        the embedding backend returns nothing.
    """
    if not outputs:
        return None
    vectors = await cf_ai_client.cf_ai_embed(outputs)
    if not vectors:
        return None
    return _centroid(vectors)
