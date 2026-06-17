# trace-core / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

The **single source of truth for all shared types and schemas** across the Sentinel monorepo. Every other package imports from here. Nothing is defined twice.

This package has **no business logic** — only schemas, types, and serialization utilities.

## Key Files

```
trace-core/
├── src/
│   ├── schema.py           ← Python Pydantic models (TraceRecord, RunManifest, EvalVerdict, ...)
│   ├── schema.ts           ← TypeScript types mirroring the Python models (for dashboard + Forge)
│   ├── otel.py             ← OTel GenAI span helpers (emit_llm_call_span, emit_tool_call_span)
│   ├── hash_utils.py       ← Canonical hash functions (normalize_request, hash_step_key)
│   └── constants.py        ← Shared constants (PASS_AT_K_TRIALS, CONFIDENCE_THRESHOLD, ...)
└── tests/
    ├── test_schema.py
    ├── test_otel.py
    └── test_hash_utils.py
```

## Critical Rules for This Package

- **Never add business logic here.** Schemas, types, constants, serialization only.
- **Python and TypeScript types must stay in sync.** When you add a field to `schema.py`, add it to `schema.ts` in the same commit.
- **Hash functions must be deterministic and stable.** `hash_step_key()` is used as the cassette lookup key in `flight-recorder`. Any change breaks existing cassettes — bump `CASSETTE_VERSION` if you must change it.
- **All constants must have a comment explaining their origin** (e.g., cite the paper, the spec, or the business reason).

## The Core Schema (reference)

```python
class TraceRecord(BaseModel):
    run_id: str
    step_id: str
    sequence: int
    timestamp: datetime
    kind: Literal["llm_call", "tool_call", "decision", "state_snapshot"]
    input: dict[str, Any]
    output: dict[str, Any]
    metadata: StepMetadata
    audit: AuditBlock

class AuditBlock(BaseModel):
    prev_hash: str     # SHA-256 of previous record's payload
    payload_hash: str  # SHA-256 of this record's canonical JSON
    hmac: str          # HMAC-SHA256 signed with AUDIT_HMAC_KEY

class EvalVerdict(BaseModel):
    run_id: str
    verdict: Literal["pass", "fail", "uncertain"]
    dimensions: dict[str, DimensionScore]
    failure_attribution: FailureAttribution | None
    self_evaluation: SelfEvaluation
    replay_link: str
    recommended_action: str
```

## Commands

```bash
make test-core      # run tests for this package
cd packages/trace-core && uv run pytest tests/ -v
cd packages/trace-core && uv run mypy src/
```
