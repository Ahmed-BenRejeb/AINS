"""Behavioural-drift detection for the eval engine (UC1 §2.3).

Compares evaluation results across runs over time and flags meaningful shifts in
agent behaviour, rubric scores, and output characteristics.
"""

from __future__ import annotations

from .detector import detect_drift
from .embedder import cosine_distance, embed_centroid

__all__ = [
    "cosine_distance",
    "detect_drift",
    "embed_centroid",
]
