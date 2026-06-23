"""Step 2 — expose WordPiece segmentation paths and counterfactual splits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from model_utils import get_tokenizer


def _wordpiece_path(text: str, tokenizer: Any) -> list[dict[str, Any]]:
    """Deterministic WordPiece path with character offsets."""
    encoding = tokenizer(
        text,
        return_offsets_mapping=True,
        add_special_tokens=False,
    )
    tokens = tokenizer.convert_ids_to_tokens(encoding["input_ids"])
    offsets = encoding["offset_mapping"]
    path: list[dict[str, Any]] = []
    for token, (start, end) in zip(tokens, offsets, strict=True):
        path.append(
            {
                "token": token,
                "start": start,
                "end": end,
                "surface": text[start:end],
                "is_subword": token.startswith("##"),
            }
        )
    return path


def _char_level_alternative(text: str) -> list[dict[str, Any]]:
    """Counterfactual path: one token per non-space character (stress test)."""
    return [
        {
            "token": ch if ch.strip() else "␠",
            "start": i,
            "end": i + 1,
            "surface": ch,
            "is_subword": False,
            "path_type": "char_level_counterfactual",
        }
        for i, ch in enumerate(text)
    ]


def _wordpiece_merge_explanation(token: str) -> list[str]:
    """Explain a WordPiece token as progressive prefix extension (pseudo merge tree)."""
    if token.startswith("##"):
        core = token[2:]
        return ["[root]", f"+ '{core}' → '{token}'"]
    steps = [token[:1]]
    for i in range(2, len(token) + 1):
        steps.append(token[:i])
    return steps


def run(samples: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    """Write segmentation path report for probe phrases."""
    tokenizer = get_tokenizer()
    probes = samples.get("segmentation_probes", [])

    entries: list[dict[str, Any]] = []
    for text in probes:
        primary = _wordpiece_path(text, tokenizer)
        alternative = _char_level_alternative(text)
        merge_notes = [
            {"token": step["token"], "merge_steps": _wordpiece_merge_explanation(step["token"])}
            for step in primary
        ]
        entries.append(
            {
                "text": text,
                "algorithm": "WordPiece (BGE / BERT tokenizer)",
                "primary_path": primary,
                "char_counterfactual_path": alternative,
                "merge_explanations": merge_notes,
                "token_count_primary": len(primary),
                "token_count_char_counterfactual": len(alternative),
            }
        )

    report = {
        "algorithm_note": (
            "BGE uses WordPiece, not BPE/Unigram. Primary path is deterministic. "
            "We include a char-level counterfactual as a 'confused lattice' baseline."
        ),
        "probes": entries,
    }
    (reports_dir / "step2_segmentation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
