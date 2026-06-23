"""Step 1 — audit tokenizer vocabulary composition."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from model_utils import get_tokenizer


def _compression_ratio(text: str, token_count: int) -> float:
    """Bytes per token for a string."""
    if token_count == 0:
        return 0.0
    return len(text.encode("utf-8")) / token_count


def _redundant_token_groups(vocab: dict[str, int]) -> list[dict[str, Any]]:
    """Find case/spacing variants that consume vocabulary capacity."""
    buckets: dict[str, list[str]] = defaultdict(list)
    for token in vocab:
        key = token.replace("##", "").strip().lower()
        if not key:
            continue
        buckets[key].append(token)
    groups = []
    for key, variants in sorted(buckets.items()):
        if len(variants) > 1:
            groups.append({"normalized": key, "variants": sorted(variants), "count": len(variants)})
    groups.sort(key=lambda g: g["count"], reverse=True)
    return groups[:50]


def run(samples: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    """Audit vocabulary composition and write report + plots."""
    tokenizer = get_tokenizer()
    vocab = tokenizer.get_vocab()

    domain_metrics: dict[str, Any] = {}
    all_token_lengths: list[int] = []

    for domain, texts in samples["domains"].items():
        ratios: list[float] = []
        token_counts: list[int] = []
        for text in texts:
            tokens = tokenizer.tokenize(text)
            token_counts.append(len(tokens))
            ratios.append(_compression_ratio(text, len(tokens)))
            all_token_lengths.extend(len(t.replace("##", "")) for t in tokens)
        domain_metrics[domain] = {
            "samples": len(texts),
            "avg_bytes_per_token": float(np.mean(ratios)) if ratios else 0.0,
            "avg_tokens_per_sample": float(np.mean(token_counts)) if token_counts else 0.0,
            "max_tokens_per_sample": max(token_counts) if token_counts else 0,
        }

    token_length_hist = Counter(all_token_lengths)
    redundant = _redundant_token_groups(vocab)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    domains = list(domain_metrics.keys())
    axes[0].bar(
        domains,
        [domain_metrics[d]["avg_bytes_per_token"] for d in domains],
        color="#34E5B0",
    )
    axes[0].set_title("Compression ratio (bytes / token) by domain")
    axes[0].tick_params(axis="x", rotation=20)

    lengths = sorted(token_length_hist.keys())
    axes[1].bar(lengths, [token_length_hist[l] for l in lengths], color="#5B9BD5")
    axes[1].set_title("Token character-length distribution")
    axes[1].set_xlabel("Token length (chars, ## stripped)")
    plt.tight_layout()
    plot_path = reports_dir / "step1_token_stats.png"
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)

    report = {
        "tokenizer_class": tokenizer.__class__.__name__,
        "vocab_size": len(vocab),
        "domain_compression": domain_metrics,
        "token_length_histogram": {str(k): v for k, v in sorted(token_length_hist.items())},
        "redundant_token_groups_top50": redundant,
        "notes": [
            "BGE uses WordPiece (BERT-style), not raw BPE merge ranks.",
            "High bytes/token on code usually means character-level fragmentation.",
        ],
        "plot": plot_path.name,
    }
    (reports_dir / "step1_vocabulary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
