# trace-core / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

The **single source of truth for all shared types and schemas** across the Sentinel monorepo. Every other package imports from here. Nothing is defined twice.

This package has **no business logic** — only schemas, types, and serialization utilities.

## Key Files

```
trace-core/
├── pyproject.toml          ← uv/hatchling package; deps: pydantic, opentelemetry-sdk
├── src/
│   └── trace_core/         ← the importable package: `from trace_core import ...`
│       ├── __init__.py     ← clean re-exports (everything importable from the top level)
│       ├── schema.py       ← Python Pydantic models (TraceRecord, RunManifest, EvalVerdict, ...)
│       ├── schema.ts       ← TypeScript types mirroring the Python models (dashboard + Forge)
│       ├── otel.py         ← OTel GenAI span helpers (emit_llm_call_span, emit_tool_call_span)
│       ├── hash_utils.py   ← Canonical hash functions (normalize_request, hash_step_key)
│       ├── constants.py    ← Shared constants (PASS_AT_K_TRIALS, CONFIDENCE_THRESHOLD, ...)
│       └── py.typed        ← PEP 561 marker so importers get our type hints
└── tests/
    ├── test_schema.py
    ├── test_otel.py
    └── test_hash_utils.py
```

> **Layout:** standard src-layout. The package is imported as `from trace_core import TraceRecord`
> — there is no `sentinel.` namespace prefix. Tooling config (mypy --strict, ruff, black, isort,
> pytest) lives in the **root** `pyproject.toml`; this package's `pyproject.toml` only declares the
> build + dependencies.

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
# Run from the repo root so the root pyproject's strict tooling config applies:
make test-core                              # pytest for this package (via Makefile)
uv run pytest packages/trace-core/tests/ -v
uv run mypy packages/trace-core             # mypy --strict (config in root pyproject.toml)
uv run ruff check packages/trace-core
```
