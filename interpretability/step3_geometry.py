"""Step 3 — analyze token embedding geometry (t-SNE + cosine audits)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from model_utils import EMBED_DIM, get_tokenizer, cosine, transformer_module


def _token_embedding_matrix() -> tuple[list[str], np.ndarray]:
    """Pull the input embedding weight matrix from the transformer."""
    model = transformer_module()
    weight = model.get_input_embeddings().weight.detach().cpu().numpy()
    tokenizer = get_tokenizer()
    id_to_token = {idx: tok for tok, idx in tokenizer.get_vocab().items()}
    tokens = [id_to_token[i] for i in range(min(len(id_to_token), weight.shape[0]))]
    return tokens, weight[: len(tokens)]


def _select_tokens_for_projection(all_tokens: list[str], probes: list[str]) -> list[int]:
    """Pick probe tokens plus common WordPiece fragments for 2D projection."""
    indices: list[int] = []
    seen: set[int] = set()
    for probe in probes:
        if probe in all_tokens:
            idx = all_tokens.index(probe)
            if idx not in seen:
                indices.append(idx)
                seen.add(idx)
    for i, tok in enumerate(all_tokens):
        if i in seen:
            continue
        if tok.startswith("##") and 2 <= len(tok) <= 8:
            indices.append(i)
            seen.add(i)
        if len(indices) >= 500:
            break
    return indices


def run(samples: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    """Project token embeddings and audit nearest neighbors."""
    all_tokens, matrix = _token_embedding_matrix()
    probe_tokens = samples.get("geometry_probe_tokens", [])
    indices = _select_tokens_for_projection(all_tokens, probe_tokens)
    sub_tokens = [all_tokens[i] for i in indices]
    sub_matrix = matrix[indices]

    from sklearn.manifold import TSNE

    perplexity = max(2, min(30, len(indices) - 1))
    coords = TSNE(n_components=2, random_state=42, perplexity=perplexity).fit_transform(sub_matrix)
    method = "tsne"

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(coords[:, 0], coords[:, 1], s=12, alpha=0.5, c="#34E5B0")
    for label in probe_tokens:
        if label in sub_tokens:
            j = sub_tokens.index(label)
            ax.annotate(label, (coords[j, 0], coords[j, 1]), fontsize=8, color="#FFB347")
    ax.set_title(f"Token embedding space ({method.upper()}, 2D)")
    plot_path = reports_dir / "step3_token_tsne.png"
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)

    # Cosine neighbor audit for suffix probes
    neighbor_audits: list[dict[str, Any]] = []
    for probe in probe_tokens:
        if probe not in all_tokens:
            continue
        idx = all_tokens.index(probe)
        vec = matrix[idx]
        sims = [(all_tokens[i], cosine(vec, matrix[i])) for i in range(len(all_tokens))]
        sims.sort(key=lambda pair: pair[1], reverse=True)
        neighbor_audits.append(
            {
                "token": probe,
                "nearest_neighbors": [
                    {"token": tok, "cosine": float(sim)} for tok, sim in sims[1:11]
                ],
            }
        )

    report = {
        "embedding_dim": EMBED_DIM,
        "tokens_projected": len(sub_tokens),
        "projection_method": method,
        "neighbor_audits": neighbor_audits,
        "plot": plot_path.name,
    }
    (reports_dir / "step3_geometry.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
