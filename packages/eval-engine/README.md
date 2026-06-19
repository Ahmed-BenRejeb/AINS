# eval-engine

**UC1 — Continuous evaluation of AI agent traces.**
Consumes OTel GenAI traces from the flight recorder and produces structured, auditable verdicts with multi-level scores, failure attribution, and `pass^k` reliability scoring.

---

## What Goes Here

- The code grader (schema validation, tool-call correctness, outcome verification, loop + token-budget checks)
- The LLM judge (**CF Workers AI Llama 3.3 70B** as judge — never Anthropic/OpenAI — with rubric scoring and mandatory position-bias calibration)
- The safety pre-filter (Llama Guard 3 via Cloudflare Workers AI)
- The DAG-based failure attributor (retrieval → planning → execution; per-step credit assignment)
- The `pass^k` metric calculator (reliability metric from τ-bench; `all()` not `any()`)
- The verdict reporter (assembles the `EvalVerdict`; files an AO Jira Incident on failure)
- The FastAPI server (entry point called by the dashboard and by UC3's evaluator step)
- _(planned)_ The drift detector (distributional shift detection across runs over time)

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

Standard src-layout: the importable package is `src/eval_engine/`
(`from eval_engine.graders.code_grader import ...`); `api.py` is at the package root.

```
eval-engine/
├── api.py                       FastAPI server (port 8000)
├── src/eval_engine/
│   ├── cf_ai_client.py          async CF Workers AI: chat / embed / safety
│   ├── config.py                env-driven config: models, thresholds, Atlassian fields
│   ├── models.py                SafetyResult, CodeGraderResult, JudgeVerdict
│   ├── transcript.py            render TraceRecords → transcript for the graders
│   ├── trace_loader.py          reconstruct a run trace from the flight recorder
│   ├── graders/
│   │   ├── code_grader.py       fast deterministic checks
│   │   ├── llm_judge.py         CF Workers AI Llama judge + position-bias calibration
│   │   └── safety_filter.py     Llama Guard 3 pre-filter
│   ├── attribution/
│   │   └── dag_attributor.py    retrieval→planning→execution failure attribution
│   ├── metrics/
│   │   └── pass_at_k.py         pass^k metric (k=8) + consistency_rate
│   └── verdicts/
│       ├── reporter.py          assemble EvalVerdict; file Jira issue on failure
│       └── atlassian_client.py  Jira create-issue (AO, type id 10013, no priority/labels)
└── tests/                       code_grader / llm_judge / pass_at_k / reporter + fixtures
```

> `drift/` (detector + embedder → Cloudflare Vectorize) is a planned extension, not yet built.

## Setup and Run

```bash
make test-uc1                                   # pytest + coverage (from repo root)
cd packages/eval-engine
uv run uvicorn api:app --reload --port 8000     # serve /evaluate, /evaluate/batch, /health
```

```python
# Evaluate one trace programmatically → one EvalVerdict
from eval_engine.verdicts.reporter import evaluate_run
verdict = await evaluate_run(run_id, trial_number=0, records=records)
```
