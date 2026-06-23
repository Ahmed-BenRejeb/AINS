# BGE dimension labeling for XQdrant retrieval explainability

Sentinel's incident agent embeds text with **BAAI/bge-base-en-v1.5** (768-dim) and searches xqdrant with `with_explanation: true`. XQdrant returns **which embedding dimensions drove each similarity score** — raw indices like `d421`, not human-readable concepts.

This folder is an **offline interpretability pipeline** that probes the same BGE model locally, maps dimensions to SRE concept labels, and produces `dimension_labels.json` for the dashboard and trace UI.

```
Incident text
    │
    ▼
atlassian-remote  embed (BGE-768)  +  xqdrant search (with_explanation)
    │                                      │
    │                                      ▼
    │                         score_explanation.top_dimensions
    │                         e.g. { "421": 0.31, "176": 0.18 }
    │                                      │
    ▼                                      ▼
flight-recorder trace          trace_core.Attribution.dims
(metadata_json on retrieval steps)
    │
    ▼
dashboard  StepTimeline → RetrievalAttribution  (shows d421 bars today)
    │
    └── dimension_labels.json  ←  this pipeline  (concept → [421, 112, …])
```

No Cloudflare keys. First run downloads ~400 MB from HuggingFace.

---

## What each step does

| Step | Module | Question it answers | Output |
|------|--------|---------------------|--------|
| **1 — Vocabulary** | `step1_vocabulary.py` | How efficiently does BGE tokenize our SRE corpus? Any redundant WordPiece entries? | `reports/step1_vocabulary.json`, token-length histogram |
| **2 — Segmentation** | `step2_segmentation.py` | How does WordPiece split incident phrases? What happens if we counterfactually split subwords into chars? | `reports/step2_segmentation.json` |
| **3 — Geometry** | `step3_geometry.py` | Do related tokens cluster in embedding space? Who are the nearest neighbors for suffix probes? | `reports/step3_geometry.json`, `step3_token_tsne.png` |
| **4 — Perturbation** | `step4_perturbation.py` | Are embeddings stable under typos and near-threshold paraphrases? | `reports/step4_perturbation.json` |
| **5 — Attribution** | `step5_attribution.py` | For each SRE concept prompt, which dims activate? Which tokens matter? | **`dimension_labels.json`**, `reports/step5_*.json` |

Steps 1–4 are **diagnostics** (reports + plots under `reports/`). Step 5 is the **deliverable** consumed by Sentinel.

### Step 5 output

**Primary file — `dimension_labels.json`** (concept → top dimension indices):

```json
{
  "Database connection pool exhaustion": [308, 237, 659, 717, 639, …],
  "API latency and timeout": [40, 41, 54, 307, …]
}
```

For each concept in `concepts.json`, the pipeline embeds its **prompt** with BGE, subtracts the **leave-one-out centroid** of all other concept prompts (removes global bias dims like 308 that fire on every text), then keeps the top `top_k` dims by |residual| (default 30).

**Audit files** (under `reports/`):

- `step5_concepts_detail.json` — full top-dim scores, integrated gradients
- `step5_token_attribution.json` — token occlusion + subword substitution probes

To resolve a raw xqdrant dim at runtime (e.g. `421`), invert the map: find which concept lists contain that index (a dim may appear under multiple concepts).

---

## How Sentinel uses the output

| Layer | Role |
|-------|------|
| **xqdrant / XQdrant fork** | Returns `top_dimensions` at search time (runtime explainability). |
| **`atlassian-remote`** | Maps those into `trace_core.Attribution.dims` and stores them on retrieval trace steps. |
| **`flight-recorder`** | Persists attribution in `metadata_json` on each vector-search tool call. |
| **Dashboard `RetrievalAttribution`** | Renders top dims as bar charts on `/runs/[run_id]`. Use **`dimension_labels.json`** to label bars with the matching SRE concept. |

After regenerating labels, copy `dimension_labels.json` into the dashboard and match xqdrant dims against each concept's list (or build an inverted index at load time).

Edit **`concepts.json`** (SRE concept prompts) and **`samples.json`** (probe corpora for steps 1–4), then re-run step 5.

---

## Setup

**Requires Python 3.11 or 3.12** — Python 3.14 is not supported yet (`torch`, etc.).

```bash
cd interpretability
rm -rf .venv                    # if you already created one on 3.14
uv python install 3.12          # one-time
uv venv --python 3.12
uv sync
source .venv/bin/activate
python -c "import sys; print(sys.version)"   # should show 3.12.x
```

**Using pip instead of uv:**

```bash
cd interpretability
python3.12 -m venv .venv && source .venv/bin/activate
pip install "torch>=2.2.0" "transformers>=4.40" "sentence-transformers>=3.0" \
  numpy matplotlib scikit-learn jupyter ipykernel
```

Runs on **CPU by default** — Apple Silicon MPS breaks integrated gradients in step 5.
Set `SENTINEL_INTERPRETABILITY_DEVICE=cuda` to use a GPU instead.

---

## Run

```bash
python build_map.py              # all 5 steps
python build_map.py --step 5     # only dimension map (after editing concepts.json)
python build_map.py --step 1,3   # vocabulary + geometry diagnostics
```

Explore results interactively:

```bash
jupyter notebook explore.ipynb
```

---

## Known limitations

- BGE uses **WordPiece**, not BPE/Unigram — no true Viterbi lattice; step 2 uses char counterfactuals instead.
- **No SHAP** — integrated gradients + token occlusion (lighter deps).
- Attribution targets **embedding dimensions** (aligned with XQdrant), not downstream LLM logits.
- Labels are **probe-derived**, not ground truth — treat as hypotheses; refine `concepts.json` and re-run.
- Raw BGE dims can include **global bias** components (large on every normalized embedding). Step 5 uses leave-one-out centroid residuals so each concept list highlights dims that differ from the other SRE probes, not universal ones like dim 308.
