"""Resolve xqdrant embedding dimensions to SRE concept labels.

Loads ``dimension_labels.json`` (concept label → top dimension indices from the
interpretability pipeline) and inverts it for runtime lookup when XQdrant returns
``score_explanation.top_dimensions``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from .config import dimension_labels_path

if TYPE_CHECKING:
    from trace_core import Attribution


@lru_cache(maxsize=1)
def _concept_to_dims() -> dict[str, list[int]]:
    """Load concept → dimension list from disk (cached)."""
    path = dimension_labels_path()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    concept_map: dict[str, list[int]] = {}
    for label, dims in raw.items():
        if not isinstance(label, str) or not isinstance(dims, list):
            continue
        concept_map[label] = [int(d) for d in dims if isinstance(d, int) or str(d).isdigit()]
    return concept_map


@lru_cache(maxsize=1)
def _dim_to_concepts() -> dict[int, list[str]]:
    """Inverted index: dimension id → concept labels that claim it."""
    inverted: dict[int, list[str]] = defaultdict(list)
    for label, dims in _concept_to_dims().items():
        for dim in dims:
            inverted[dim].append(label)
    return dict(inverted)


def clear_dimension_label_cache() -> None:
    """Drop cached label maps (for tests or hot reload)."""
    _concept_to_dims.cache_clear()
    _dim_to_concepts.cache_clear()


def resolve_terms(dims: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    """Map raw dimension contributions to aggregated concept-label contributions.

    Args:
        dims: Per-dimension scores from xqdrant (string keys).

    Returns:
        ``(terms, unmapped_dims)`` — ``terms`` sums contributions by concept label;
        ``unmapped_dims`` lists dimension ids with no entry in the label map.
    """
    if not dims:
        return {}, []

    inverted = _dim_to_concepts()
    terms: dict[str, float] = defaultdict(float)
    unmapped: list[str] = []

    for dim_str, contribution in dims.items():
        try:
            dim_id = int(dim_str)
        except ValueError:
            unmapped.append(dim_str)
            continue
        labels = inverted.get(dim_id, [])
        if not labels:
            unmapped.append(dim_str)
            continue
        share = float(contribution) / len(labels)
        for label in labels:
            terms[label] += share

    return dict(terms), unmapped


def enrich_attribution(attribution: Attribution) -> Attribution:
    """Fill ``Attribution.terms`` from ``Attribution.dims`` using the label map."""
    from trace_core import Attribution

    if not attribution.dims:
        return attribution
    terms, _unmapped = resolve_terms(attribution.dims)
    if terms:
        return attribution.model_copy(update={"terms": terms})
    if attribution.terms:
        return attribution  # legacy payload terms when dims do not map
    return attribution.model_copy(update={"terms": {}})


def unmapped_dimensions(dims: dict[str, float]) -> list[str]:
    """Return dimension ids from ``dims`` that have no concept label."""
    _terms, unmapped = resolve_terms(dims)
    return unmapped
