"""Step 5 — downstream attribution: dimensions, token occlusion, substitution probing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

from model_utils import (
    MODEL_NAME,
    embed_texts,
    get_tokenizer,
    resolve_torch_device,
    top_distinctive_dimensions,
    transformer_module,
    cosine,
)


def _mean_pool(last_hidden: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Mean-pool token hidden states (BGE-style)."""
    mask = attention_mask.unsqueeze(-1).float()
    summed = (last_hidden * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def _integrated_gradients_dims(text: str, target_dims: list[int], steps: int = 24) -> list[float]:
    """Integrated-gradient mass per output dimension (scalar, one entry per target dim)."""
    if not target_dims:
        return []

    device = resolve_torch_device()
    tokenizer = get_tokenizer()
    model = transformer_module().to(device)
    model.eval()

    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded["attention_mask"].to(device)
    embed_layer = model.get_input_embeddings()
    baseline = torch.zeros_like(embed_layer(input_ids))

    per_dim_scores: list[float] = []
    for target_dim in target_dims:
        accumulated = torch.zeros(input_ids.shape[1], dtype=torch.float32)
        for step in range(1, steps + 1):
            alpha = step / steps
            inputs_embeds = baseline + alpha * (embed_layer(input_ids) - baseline)
            inputs_embeds = inputs_embeds.detach().requires_grad_(True)
            model.zero_grad(set_to_none=True)
            outputs = model(inputs_embeds=inputs_embeds, attention_mask=attention_mask)
            pooled = _mean_pool(outputs.last_hidden_state, attention_mask)
            score = pooled[0, target_dim]
            score.backward()
            grad = inputs_embeds.grad.detach().abs().sum(dim=-1).squeeze(0).cpu()
            accumulated += grad
        per_dim_scores.append(float(accumulated.sum() / steps))

    return per_dim_scores


def _token_occlusion(text: str, reference: np.ndarray) -> list[dict[str, Any]]:
    """Zero each token in turn; measure cosine drop vs reference embedding."""
    tokenizer = get_tokenizer()
    tokens = tokenizer.tokenize(text)
    if not tokens:
        return []
    encoded = tokenizer(text, return_offsets_mapping=True, add_special_tokens=True)
    input_ids = encoded["input_ids"]
    id_tokens = tokenizer.convert_ids_to_tokens(input_ids)

    base_vec = embed_texts([text])[0]
    results: list[dict[str, Any]] = []
    for i in range(1, len(input_ids) - 1):  # skip [CLS]/[SEP]
        masked_ids = list(input_ids)
        masked_ids[i] = tokenizer.unk_token_id
        masked_text = tokenizer.decode(masked_ids, skip_special_tokens=True)
        masked_vec = embed_texts([masked_text])[0]
        results.append(
            {
                "token": id_tokens[i],
                "position": i,
                "cosine_to_reference": cosine(masked_vec, reference),
                "cosine_drop_from_full": cosine(base_vec, masked_vec),
            }
        )
    results.sort(key=lambda row: row["cosine_drop_from_full"])
    return results


def _substitution_probe(text: str, tokenizer: Any) -> list[dict[str, Any]]:
    """Replace subwords with char-split counterfactual; measure embedding shift."""
    tokens = tokenizer.tokenize(text)
    base_vec = embed_texts([text])[0]
    probes: list[dict[str, Any]] = []
    for i, tok in enumerate(tokens):
        if not tok.startswith("##"):
            continue
        chars = list(tok.replace("##", ""))
        alt_tokens = tokens[:i] + chars + tokens[i + 1 :]
        alt_text = tokenizer.convert_tokens_to_string(alt_tokens)
        alt_vec = embed_texts([alt_text])[0]
        probes.append(
            {
                "original_token": tok,
                "position": i,
                "substitution": alt_text,
                "embedding_cosine_to_original": cosine(base_vec, alt_vec),
            }
        )
    return probes


def build_dimension_labels(
    concepts: list[dict[str, Any]],
    *,
    top_k: int,
    dimensions: int,
    reports_dir: Path,
) -> dict[str, list[int]]:
    """Map each concept label to its top embedding dimensions (from BGE probe prompts)."""
    concept_map: dict[str, list[int]] = {}
    enriched: list[dict[str, Any]] = []
    attribution_report: list[dict[str, Any]] = []

    prompts = [str(concept["prompt"]) for concept in concepts]
    all_vectors = embed_texts(prompts)

    for index, concept in enumerate(concepts):
        label = str(concept["label"])
        concept_id = str(concept["id"])
        prompt = prompts[index]
        vector = all_vectors[index]
        reference = np.delete(all_vectors, index, axis=0)
        tops = top_distinctive_dimensions(vector, reference, top_k)
        concept_map[label] = [int(entry["dimension"]) for entry in tops]

        ig_dims = [int(d["dimension"]) for d in tops[:5]]
        ig_scores = _integrated_gradients_dims(prompt, ig_dims)
        reference = vector
        occlusion = _token_occlusion(prompt, reference)
        substitution = _substitution_probe(prompt, get_tokenizer())

        enriched.append(
            {
                "id": concept_id,
                "label": label,
                "prompt": prompt,
                "top_dimensions": tops,
                "integrated_gradients_on_top_dims": [
                    {"dimension": d, "token_mass": float(s)}
                    for d, s in zip(ig_dims, ig_scores, strict=True)
                ],
            }
        )
        attribution_report.append(
            {
                "concept_id": concept_id,
                "label": label,
                "token_occlusion": occlusion[:10],
                "subword_substitution_probes": substitution[:5],
            }
        )

    detail = {
        "meta": {
            "model": MODEL_NAME,
            "embedding_dimensions": dimensions,
            "top_k": top_k,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "methods": [
                "top_distinctive_dimensions_loo_centroid",
                "integrated_gradients_on_top_dims",
                "token_occlusion",
                "subword_substitution_probe",
            ],
        },
        "concepts": enriched,
    }
    (reports_dir / "step5_concepts_detail.json").write_text(
        json.dumps(detail, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (reports_dir / "step5_token_attribution.json").write_text(
        json.dumps({"concepts": attribution_report}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return concept_map


def run(
    concepts: list[dict[str, Any]],
    spec: dict[str, Any],
    reports_dir: Path,
) -> dict[str, list[int]]:
    """Run step 5; return concept label → top dimension indices."""
    return build_dimension_labels(
        concepts,
        top_k=int(spec.get("top_k", 30)),
        dimensions=int(spec.get("embedding_dimensions", 768)),
        reports_dir=reports_dir,
    )
