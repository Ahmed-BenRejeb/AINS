"""Load BGE-base-en-v1.5 locally — same model family as CF Workers AI / xqdrant seed."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import numpy as np

MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBED_DIM = 768


if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    from transformers import PreTrainedTokenizerBase


def resolve_torch_device() -> str:
    """Return torch device for this pipeline (CPU default — MPS breaks IG on Mac)."""
    return os.environ.get("SENTINEL_INTERPRETABILITY_DEVICE", "cpu")


@lru_cache(maxsize=1)
def get_tokenizer() -> PreTrainedTokenizerBase:
    """Return the BGE WordPiece tokenizer."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(MODEL_NAME)


@lru_cache(maxsize=1)
def get_sentence_model() -> SentenceTransformer:
    """Return the SentenceTransformer wrapper for BGE."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME, device=resolve_torch_device())


def embed_texts(texts: list[str], *, normalize: bool = True) -> np.ndarray:
    """Encode texts to 768-d vectors."""
    if not texts:
        return np.empty((0, EMBED_DIM), dtype=np.float32)
    vectors = get_sentence_model().encode(
        texts,
        normalize_embeddings=normalize,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def top_dimensions(vector: np.ndarray, k: int) -> list[dict[str, float | int]]:
    """Top-k dimensions by absolute activation on a (typically L2-normalized) vector."""
    ranked = sorted(enumerate(vector.tolist()), key=lambda pair: abs(pair[1]), reverse=True)
    return [{"dimension": int(i), "contribution": float(v)} for i, v in ranked[:k]]


def top_distinctive_dimensions(
    vector: np.ndarray,
    reference_vectors: np.ndarray,
    k: int,
) -> list[dict[str, float | int]]:
    """Top-k dims by |deviation| from a reference centroid.

    BGE outputs L2-normalized embeddings; a few dims (e.g. 308) have large
    magnitude on *every* text. Ranking raw activations always surfaces those
    global bias dims. Subtracting a reference centroid (leave-one-out over
    sibling concept prompts) keeps concept-specific dimensions.
    """
    if reference_vectors.size == 0:
        return top_dimensions(vector, k)
    centroid = reference_vectors.mean(axis=0)
    residual = vector - centroid
    ranked = sorted(enumerate(residual.tolist()), key=lambda pair: abs(pair[1]), reverse=True)
    return [{"dimension": int(i), "contribution": float(v)} for i, v in ranked[:k]]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def transformer_module() -> Any:
    """Underlying HuggingFace transformer (first ST module)."""
    return get_sentence_model()[0].auto_model
