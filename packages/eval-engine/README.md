# eval-engine

**UC1 — Continuous evaluation of AI agent traces.**
Consumes OTel GenAI traces from the flight recorder and produces structured, auditable verdicts with multi-level scores, failure attribution, and drift detection.

---

## What Goes Here

- The code grader (schema validation, tool-call correctness, outcome verification)
- The LLM judge (Claude-as-judge with rubric scoring and position-bias calibration)
- The safety pre-filter (Llama Guard 3 via Cloudflare Workers AI)
- The DAG-based failure attributor (per-step failure probabilities)
- The drift detector (distributional shift detection across runs over time)
- The `pass^k` metric calculator (reliability metric from τ-bench)
- The verdict reporter (formats verdicts as human-readable reports + Jira issue bodies)
- The FastAPI server (entry point called by the dashboard and by UC3's evaluator step)

## What Does NOT Go Here

- Trace capture/recording — that is `flight-recorder`
- Atlassian API calls — that is `atlassian-remote`
- UI rendering — that is `dashboard`

## Why It Exists

Traditional unit tests fail for non-deterministic AI agents because they assume exact output matching. The eval engine uses a three-grader approach (code + LLM + human) to evaluate *trajectories*, not just outputs. It is separate from the flight recorder because these are independent concerns: you can evaluate any trace regardless of how it was recorded, and you can record any run without evaluating it.

## Key Research Foundations

| Concept | Source |
|---|---|
| `pass^k` reliability metric | τ-bench (arXiv 2406.12045) |
| Transcript vs. outcome distinction | Anthropic "Demystifying evals" (Jan 2026) |
| Judge calibration (position bias, length bias) | AgentRewardBench (arXiv 2504.08942) |
| Per-step failure attribution | VeriLA pattern |

## Structure

```
eval-engine/
├── src/
│   ├── graders/
│   │   ├── code_grader.py       fast deterministic checks
│   │   ├── llm_judge.py         Claude-as-judge with calibration
│   │   └── safety_filter.py     Llama Guard 3 pre-filter
│   ├── attribution/
│   │   └── dag_attributor.py    per-component failure probabilities
│   ├── drift/
│   │   ├── detector.py          distributional shift detection
│   │   └── embedder.py          embed outputs → Cloudflare Vectorize
│   ├── metrics/
│   │   └── pass_at_k.py         pass^k metric (run k=8 trials)
│   ├── verdicts/
│   │   └── reporter.py          format verdict as report + Jira issue body
│   └── api.py                   FastAPI server
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/                sample traces + expected verdicts
```

## Setup and Run

```bash
cd packages/eval-engine
uv sync
uv run pytest tests/ -v
uv run uvicorn api:app --reload --port 8000

# Evaluate a specific run
uv run python -m sentinel.eval_engine.evaluate --run-id <uuid> --k 8
```
