"""Step 4 — perturbation and robustness tests on tokenization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from model_utils import embed_texts, cosine, get_tokenizer


def _typo_variants(text: str) -> list[tuple[str, str]]:
    """Single-character typos for robustness probes."""
    variants: list[tuple[str, str]] = []
    for i, ch in enumerate(text):
        if not ch.isalpha():
            continue
        chars = list(text)
        chars[i] = "z" if ch.lower() != "z" else "x"
        variants.append((f"swap_{i}_{ch}", "".join(chars)))
    return variants[:12]


def _boundary_variants(text: str) -> list[tuple[str, str]]:
    """Spacing and punctuation counterfactuals."""
    return [
        ("leading_space", f" {text}"),
        ("trailing_space", f"{text} "),
        ("wrap_parens", f"({text})"),
        ("wrap_quotes", f'"{text}"'),
        ("double_space", text.replace(" ", "  ", 1) if " " in text else text),
    ]


def _token_delta(base_tokens: list[str], variant_tokens: list[str]) -> dict[str, Any]:
    """Summarize how much tokenization changed."""
    return {
        "base_count": len(base_tokens),
        "variant_count": len(variant_tokens),
        "count_delta": len(variant_tokens) - len(base_tokens),
        "jaccard_token_set": len(set(base_tokens) & set(variant_tokens))
        / max(len(set(base_tokens) | set(variant_tokens)), 1),
        "base_tokens": base_tokens,
        "variant_tokens": variant_tokens,
    }


def run(samples: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    """Stress-test tokenizer + embedding stability under perturbations."""
    tokenizer = get_tokenizer()
    base = samples.get("perturbation_base", "")
    base_tokens = tokenizer.tokenize(base)
    base_vec = embed_texts([base])[0]

    typo_results: list[dict[str, Any]] = []
    for label, variant in _typo_variants(base):
        v_tokens = tokenizer.tokenize(variant)
        v_vec = embed_texts([variant])[0]
        typo_results.append(
            {
                "label": label,
                "text": variant,
                "token_delta": _token_delta(base_tokens, v_tokens),
                "embedding_cosine_to_base": cosine(base_vec, v_vec),
            }
        )

    boundary_results: list[dict[str, Any]] = []
    for label, variant in _boundary_variants(base):
        v_tokens = tokenizer.tokenize(variant)
        v_vec = embed_texts([variant])[0]
        boundary_results.append(
            {
                "label": label,
                "text": variant,
                "token_delta": _token_delta(base_tokens, v_tokens),
                "embedding_cosine_to_base": cosine(base_vec, v_vec),
            }
        )

    report = {
        "base_text": base,
        "base_token_count": len(base_tokens),
        "typo_tests": typo_results,
        "boundary_tests": boundary_results,
        "risk_flags": [
            r for r in typo_results + boundary_results if r["embedding_cosine_to_base"] < 0.85
        ],
    }
    (reports_dir / "step4_perturbation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
