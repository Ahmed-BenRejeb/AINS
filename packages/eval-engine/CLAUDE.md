# eval-engine / CLAUDE.md

> Read the root `CLAUDE.md` first, especially Section 0 (deployed infra) and Section 7 (CF Workers AI pattern).
> This package runs on the Azure VM at port 8000, exposed at `eval.ahmedxsaad.me`.

## What This Package Does

**UC1: The continuous evaluation system.**
Consumes OTel GenAI traces from the flight recorder, runs them through a multi-level grader pipeline,
and produces `EvalVerdict` objects with failure attribution, `pass^k` scores, and self-evaluation confidence.

## Key Files

> **Layout:** standard src-layout — the importable package is `src/eval_engine/`,
> imported as `from eval_engine.graders.code_grader import ...` (repo convention; on-disk
> path == import path keeps `mypy --strict` clean). `api.py` is at the package root, run
> with `uvicorn api:app --port 8000`.

```
eval-engine/
├── api.py                       FastAPI server (port 8000): /evaluate /evaluate/batch /drift /health
├── pyproject.toml               hatchling package; deps: trace-core, httpx, fastapi
├── src/eval_engine/
│   ├── cf_ai_client.py          async CF Workers AI: cf_ai_chat / cf_ai_embed / cf_ai_safety (429/5xx retry+backoff in _post)
│   ├── config.py                env-driven config: models, thresholds, Atlassian fields
│   ├── models.py                local result models: SafetyResult, CodeGraderResult, JudgeVerdict
│   ├── transcript.py            render a run's TraceRecords into a judge/safety transcript
│   ├── cassette_store.py        boto3 read of the full run cassette from MinIO (non-lossy)
│   ├── trace_loader.py          load a run trace — cassette first, D1 previews as fallback
│   ├── graders/
│   │   ├── code_grader.py       fast deterministic checks (schema, tool calls, outcome, loop, tokens)
│   │   ├── llm_judge.py         CF Workers AI Llama judge — rubric scoring + position-bias calibration
│   │   └── safety_filter.py     Llama Guard 3 via CF Workers AI pre-filter
│   ├── attribution/
│   │   └── dag_attributor.py    VeriLA-style retrieval→planning→execution failure attribution
│   ├── metrics/
│   │   └── pass_at_k.py         pass^k metric (k=8, τ-bench standard) + consistency_rate
│   ├── drift/
│   │   ├── embedder.py          BGE output-centroid embedding + cosine_distance (via cf_ai_embed)
│   │   └── detector.py          detect_drift(baseline, current) → DriftReport (UC1 §2.3)
│   └── verdicts/
│       ├── reporter.py          orchestrates the pipeline → EvalVerdict; files Jira issue (best-effort)
│       └── atlassian_client.py  minimal Jira create-issue (AO, type id 10013, no priority/labels)
└── tests/
    ├── test_code_grader / test_llm_judge / test_pass_at_k / test_reporter / test_trace_loader / test_cf_ai_response
    └── fixtures/
        ├── trace_pass.json      trace that should pass
        └── trace_fail_step2.json trace that should fail at step 2 (retrieval)
```

> **Drift detection** (`drift/detector.py` + `embedder.py`) is **built** (UC1 §2.3).
> `detect_drift(baseline, current)` compares two windows of `EvalVerdict`s and returns a
> shared `trace_core.DriftReport`: pass-rate delta, per-dimension score deltas, and —
> when output text is supplied — semantic drift (cosine distance of BGE output-centroid
> embeddings via `cf_ai_embed`, the same path `atlassian-remote` uses for xqdrant). A
> signal crossing its `DRIFT_*` threshold (config.py) sets `drift_detected`.

## LLM Judge — CF Workers AI Pattern

```python
# Uses CF Workers AI Llama 3.3 70B for judging
# See root CLAUDE.md Section 7 for the exact call pattern
# Model: os.environ["CF_AI_MODEL_MAIN"] = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

async def llm_judge(transcript: str, rubric: str) -> JudgeVerdict:
    messages = [
        {"role": "system", "content": "You are a precise AI system evaluator. Output JSON only."},
        {"role": "user", "content": f"Rubric:\n{rubric}\n\nTranscript:\n{transcript}\n\nOutput JSON verdict."}
    ]
    raw = await cf_ai_chat(messages)  # from cf_ai_client.py
    return JudgeVerdict.model_validate_json(raw)
```

## Judge Calibration (MANDATORY — never skip)

```python
# graders/llm_judge.py — judge the SAME transcript twice with the rubric
# dimensions presented in opposite order. A verdict flip means the judge is
# order-sensitive on this case, so the result is downgraded to "uncertain".
async def calibrated_judge(transcript: str, rubric: str = DEFAULT_RUBRIC) -> JudgeVerdict:
    primary = await judge(transcript, rubric)
    swapped = await judge(transcript, _reorder_rubric(rubric))  # dimensions reversed
    if primary.verdict != swapped.verdict:
        return JudgeVerdict(verdict="uncertain", flag_for_human=True,
                            reason="position_bias_detected", ...)
    return JudgeVerdict(verdict=primary.verdict, flag_for_human=False, ...)

# Each pass's verdict is derived from the mean dimension score vs
# JUDGE_PASS_THRESHOLD (0.6). The reporter additionally flags for human review
# when judge confidence < CONFIDENCE_THRESHOLD (0.70, from trace_core).
```

## pass^k Metric (k=8)

```python
PASS_AT_K_TRIALS = 8  # from trace-core constants

def pass_at_k(results: list[bool]) -> float:
    """True pass^k: all k trials must succeed."""
    return float(all(results[:PASS_AT_K_TRIALS]))

def consistency_rate(results: list[bool]) -> float:
    return sum(results) / len(results) if results else 0.0
```

## Atlassian — File Verdict as Jira Issue

```python
# When verdict = "fail" or flag_for_human = True:
# Create issue in AO project with issue type ID 10013
# Do NOT include priority or labels fields
post(f"{JIRA_URL}/issue", {
    "fields": {
        "project": {"key": "AO"},
        "summary": f"Sentinel eval failure: {run_id[:8]}",
        "issuetype": {"id": "10013"},   # [System] Incident — use ID not name
        "description": {...}            # ADF format, verdict details
    }
})
```

## Critical Rules

- **LLM judge uses CF Workers AI** — not Anthropic, not OpenAI
- **Position-bias calibration is mandatory** — run every judgment twice
- **pass^k not pass@1** — `all(results[:8])` not `any(results[:8])`
- **Tests must mock all external calls** — use `pytest-httpx`

## Commands

```bash
make test-uc1                                   # pytest + coverage for this package
uv run mypy packages/eval-engine                # mypy --strict (config in root pyproject)
uv run ruff check packages/eval-engine
cd packages/eval-engine && uv run uvicorn api:app --reload --port 8000
```

Programmatic usage (one trace → one verdict):

```python
from eval_engine.verdicts.reporter import evaluate_run

# records: list[TraceRecord] for one run (load via eval_engine.trace_loader.load_trace)
verdict = await evaluate_run(run_id, trial_number=0, records=records)
# verdict.verdict ∈ {"pass","fail","uncertain"}; verdict.failure_attribution; verdict.self_evaluation
```

## Status (20 Jun 2026)

Core pipeline built, green, and **live-validated** by the Phase 4 loop: `make
test-uc1` passes (39 tests); ruff/black/isort/mypy --strict clean. `trace_loader`
now loads the **full MinIO cassette** via `cassette_store` (D1 row previews are the
fallback only). Jira filing in `reporter._file_issue` is **best-effort** (a Jira
outage/rejection no longer fails `/evaluate`). `cf_ai_chat` re-serializes CF Workers
AI's JSON-mode dict response to a string so the judge can `model_validate_json` it.
`cf_ai_client._post` retries CF Workers AI rate limits / transient 5xx (429 → 30s
×3, 5xx → 5s ×2, via `asyncio.sleep`); LLM calls are also traced to Langfuse.

**Drift detection (UC1 §2.3) is now built** (`drift/embedder.py` + `drift/detector.py`,
`POST /drift`): `detect_drift` compares a baseline vs current window of `EvalVerdict`s
on pass-rate, per-dimension scores, and (optionally) semantic output-embedding drift,
returning a `trace_core.DriftReport`. Thresholds live in `config.py` (`DRIFT_*`).