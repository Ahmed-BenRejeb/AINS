# eval-engine / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**UC1: The continuous evaluation system.** Consumes OTel GenAI traces from `flight-recorder`, runs them through a multi-level grader pipeline, and produces `EvalVerdict` objects with failure attribution, `pass^k` reliability scores, and self-evaluation confidence.

## Key Files

```
eval-engine/
├── src/
│   ├── graders/
│   │   ├── code_grader.py       ← fast, deterministic checks (schema, tool calls, outcome)
│   │   ├── llm_judge.py         ← Claude-as-judge: rubric scoring + position-bias calibration
│   │   └── safety_filter.py     ← Llama Guard 3 via Workers AI (pre-filter before judge)
│   ├── attribution/
│   │   └── dag_attributor.py    ← VeriLA-style DAG: per-component failure probabilities
│   ├── drift/
│   │   ├── detector.py          ← distributional drift detection across runs
│   │   └── embedder.py          ← embed outputs → Cloudflare Vectorize
│   ├── metrics/
│   │   └── pass_at_k.py         ← pass^k metric (τ-bench standard, k=8 by default)
│   ├── verdicts/
│   │   ├── schema.py            ← re-exports from trace-core (no duplication)
│   │   └── reporter.py          ← formats verdict as human-readable report + Jira issue body
│   └── api.py                   ← FastAPI server (called by Forge Remote + dashboard)
└── tests/
    ├── unit/
    │   ├── test_code_grader.py
    │   ├── test_llm_judge.py      ← uses recorded judge responses, no live API in unit tests
    │   └── test_pass_at_k.py
    ├── integration/
    │   └── test_eval_pipeline.py  ← full pipeline on fixture traces
    └── fixtures/
        ├── trace_pass.json         ← a trace that should produce verdict="pass"
        ├── trace_fail_step2.json   ← a trace that should fail at step 2 (retrieval)
        ├── trace_fail_step4.json   ← a trace that should fail at step 4 (RCA quality)
        └── judge_responses/        ← pre-recorded Claude judge responses for unit tests
```

## The Evaluation Pipeline

```
Trace (OTel gen_ai.* spans from D1/R2)
    │
    ▼
[1. Safety Filter]   → Llama Guard 3 on Workers AI (fast, cheap)
    │ passes
    ▼
[2. Code Grader]     → schema validity, tool correctness, outcome check
    │ scores + failure flags
    ▼
[3. LLM Judge]       → rubric scoring, position-bias calibration, self-critique
    │ per-dimension scores
    ▼
[4. DAG Attributor]  → which step caused the failure? (VeriLA pattern)
    │ failure_attribution
    ▼
[5. pass^k]          → run k=8 independent trials, compute consistency rate
    │ reliability metric
    ▼
[EvalVerdict]        → stored in D1, filed as Jira issue if verdict="fail"
```

## Critical Rules for This Package

- **Never call the Anthropic API directly** — always use the shared client from `atlassian-remote/anthropic_client.py` which handles rate limiting and logging.
- **Unit tests must NOT call live APIs.** Pre-record judge responses in `tests/fixtures/judge_responses/` and mock with `pytest-httpx`. The `test_llm_judge.py` module shows the pattern.
- **Position-bias calibration is mandatory.** Every LLM judge call runs the pair twice with swapped order. If the verdict flips, mark as `"uncertain"` and `flag_for_human: true`. Never skip this.
- **Grader stages are independent.** If the safety filter fails, short-circuit and skip the judge. If the code grader already produces `verdict="fail"` with high confidence, you can skip the full judge call (save cost). Document this in the verdict's `grader_path` field.

## Key Constants (in `constants.py` from trace-core)

```python
PASS_AT_K_TRIALS = 8              # k for pass^k metric — τ-bench standard
CONFIDENCE_THRESHOLD = 0.70       # below this → flag_for_human = True
SAFETY_SCORE_THRESHOLD = 0.95     # Llama Guard score below this → abort
MAX_JUDGE_RETRIES = 3             # retry judge call on transient failure
```

## Known Gotchas

- **LLM judges have position bias.** Always run each judgment twice with swapped order. See `llm_judge.py:calibrated_judge()`. This is not optional.
- **pass^k is not the same as pass@1.** `pass@1` = at least one success. `pass^k` = ALL k trials succeed. Our metric is `pass^k`. The math is `all(results[:k])` not `any(results[:k])`.
- **Drift detection needs a baseline.** The first time you run `drift/detector.py` for an agent, it writes a baseline fingerprint. Drift is detected on subsequent runs. Don't test drift detection with a single run.

## Commands

```bash
make test-uc1
cd packages/eval-engine && uv run uvicorn api:app --reload --port 8000
uv run python -m sentinel.eval_engine.evaluate --run-id <run_id>
uv run python -m sentinel.eval_engine.evaluate --run-id <run_id> --k 8
```
