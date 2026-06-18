# eval-engine / CLAUDE.md

> Read the root `CLAUDE.md` first, especially Section 0 (deployed infra) and Section 7 (CF Workers AI pattern).
> This package runs on the Azure VM at port 8000, exposed at `eval.ahmedxsaad.me`.

## What This Package Does

**UC1: The continuous evaluation system.**
Consumes OTel GenAI traces from the flight recorder, runs them through a multi-level grader pipeline,
and produces `EvalVerdict` objects with failure attribution, `pass^k` scores, and self-evaluation confidence.

## Key Files

```
eval-engine/
├── src/
│   ├── graders/
│   │   ├── code_grader.py       fast deterministic checks (schema, tool calls, outcome)
│   │   ├── llm_judge.py         CF Workers AI as judge — rubric scoring + bias calibration
│   │   └── safety_filter.py     Llama Guard 3 via CF Workers AI pre-filter
│   ├── attribution/
│   │   └── dag_attributor.py    VeriLA-style per-component failure probabilities
│   ├── drift/
│   │   ├── detector.py          distributional shift detection
│   │   └── embedder.py          embed via CF Workers AI → Cloudflare Vectorize
│   ├── metrics/
│   │   └── pass_at_k.py         pass^k metric (k=8, τ-bench standard)
│   ├── verdicts/
│   │   └── reporter.py          format verdict + file Jira issue
│   └── api.py                   FastAPI server
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
        ├── trace_pass.json      trace that should pass
        └── trace_fail_step2.json trace that should fail at step 2 (retrieval)
```

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
async def calibrated_judge(a: str, b: str) -> CalibratedVerdict:
    v1 = await llm_judge(a, b)
    v2 = await llm_judge(b, a)  # swapped order
    if v1.winner != flip(v2.winner):
        return CalibratedVerdict(verdict="uncertain", flag_for_human=True, reason="position_bias_detected")
    return CalibratedVerdict(verdict=v1.winner, flag_for_human=False)
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
make test-uc1
cd packages/eval-engine && uv run uvicorn api:app --reload --port 8000
uv run python -m sentinel.eval_engine.evaluate --run-id <uuid> --k 8
```