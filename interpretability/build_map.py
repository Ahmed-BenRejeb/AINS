#!/usr/bin/env python3
"""Run the 5-step BGE interpretability pipeline (local model, no Cloudflare).

    python build_map.py              # all steps
    python build_map.py --step 5     # only dimension map + attribution
    python build_map.py --step 1,3   # vocabulary + geometry

First run downloads ``BAAI/bge-base-en-v1.5`` (~400MB) via HuggingFace.
Outputs:
  - reports/step1_vocabulary.json … step5_token_attribution.json (+ plots)
  - dimension_labels.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import step1_vocabulary
import step2_segmentation
import step3_geometry
import step4_perturbation
import step5_attribution

ROOT = Path(__file__).resolve().parent
CONCEPTS_PATH = ROOT / "concepts.json"
SAMPLES_PATH = ROOT / "samples.json"
LABELS_PATH = ROOT / "dimension_labels.json"
REPORTS_DIR = ROOT / "reports"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(steps: set[int] | None = None) -> dict:
    """Execute selected pipeline steps; always writes dimension_labels on step 5."""
    REPORTS_DIR.mkdir(exist_ok=True)
    samples = _load_json(SAMPLES_PATH)
    spec = _load_json(CONCEPTS_PATH)
    concepts = spec.get("concepts", [])
    if not concepts:
        raise ValueError("concepts.json has no concepts")

    selected = steps or {1, 2, 3, 4, 5}
    summary: dict = {"steps_run": sorted(selected), "reports_dir": str(REPORTS_DIR)}

    if 1 in selected:
        print("→ Step 1: vocabulary audit …")
        summary["step1"] = step1_vocabulary.run(samples, REPORTS_DIR)

    if 2 in selected:
        print("→ Step 2: segmentation paths …")
        summary["step2"] = step2_segmentation.run(samples, REPORTS_DIR)

    if 3 in selected:
        print("→ Step 3: embedding geometry …")
        summary["step3"] = step3_geometry.run(samples, REPORTS_DIR)

    if 4 in selected:
        print("→ Step 4: perturbation tests …")
        summary["step4"] = step4_perturbation.run(samples, REPORTS_DIR)

    concept_map: dict[str, list[int]] | None = None
    if 5 in selected:
        print(f"→ Step 5: attribution + dimension map ({len(concepts)} concepts) …")
        concept_map = step5_attribution.run(concepts, spec, REPORTS_DIR)
        LABELS_PATH.write_text(json.dumps(concept_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary["dimension_labels"] = {
            "concepts": len(concept_map),
            "dims_per_concept": len(next(iter(concept_map.values()), [])),
            "path": str(LABELS_PATH.name),
        }

    return summary if concept_map is None else concept_map


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="BGE interpretability pipeline")
    parser.add_argument(
        "--step",
        type=str,
        default="all",
        help="Steps to run: all, or comma-separated 1-5 (e.g. 1,3,5)",
    )
    args = parser.parse_args()

    if not CONCEPTS_PATH.is_file():
        print(f"Missing {CONCEPTS_PATH}", file=sys.stderr)
        return 1
    if not SAMPLES_PATH.is_file():
        print(f"Missing {SAMPLES_PATH}", file=sys.stderr)
        return 1

    if args.step == "all":
        steps = None
    else:
        steps = {int(part.strip()) for part in args.step.split(",") if part.strip()}

    try:
        result = run(steps)
    except Exception as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1

    if isinstance(result, dict) and result and isinstance(next(iter(result.values())), list):
        sample_label = next(iter(result))
        print(
            f"✓ wrote {LABELS_PATH.name} — "
            f"{len(result)} concepts, "
            f"{len(result[sample_label])} dims each (top_k)"
        )
        print(f"  reports → {REPORTS_DIR}/")
    else:
        print(f"✓ reports → {REPORTS_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
