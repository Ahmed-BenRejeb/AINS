# trace-core

**The shared contract for all of Sentinel.**
One rule: if a type or constant is used by more than one package, it lives here.

---

## What Goes Here

- Pydantic models (Python) for every data structure that crosses a package boundary
- TypeScript mirrors of those models (for the dashboard and Forge app)
- OTel GenAI span helpers (`emit_llm_call_span`, `emit_tool_call_span`)
- Canonical hash/normalization functions used by the flight recorder's cassette system
- Shared constants (`PASS_AT_K_TRIALS=8`, `CONFIDENCE_THRESHOLD=0.70`, `CASSETTE_VERSION`, etc.)

## What Does NOT Go Here

- Business logic of any kind
- API calls, database queries, HTTP requests
- Anything that imports from another local package

## Why It Exists

Without `trace-core`, every package would define its own `TraceRecord` or `EvalVerdict` model. They would drift out of sync. The flight recorder would produce a shape the eval engine can't read. `trace-core` is the contract that prevents this — it is imported by everyone and imports nothing local.

## Usage

Standard src-layout. Import everything from the top-level package — no `sentinel.` prefix:

```python
from trace_core import TraceRecord, EvalVerdict, PASS_AT_K_TRIALS
```

## Structure

```
trace-core/
├── pyproject.toml       Build + dependencies (tooling config is in the root pyproject.toml)
├── src/
│   └── trace_core/      The importable package (`from trace_core import ...`)
│       ├── __init__.py  Clean re-exports of everything below
│       ├── schema.py    All Pydantic models: TraceRecord, EvalVerdict, AuditBlock, StepMetadata
│       ├── schema.ts    TypeScript mirrors — must stay in sync with schema.py
│       ├── otel.py      OTel GenAI span helpers (gen_ai.* semantic conventions)
│       ├── hash_utils.py Canonical request normalization + SHA-256 hashing
│       ├── constants.py All named constants with a comment explaining each value's origin
│       └── py.typed     PEP 561 marker so importers get our type hints
└── tests/
    ├── test_schema.py
    ├── test_otel.py
    └── test_hash_utils.py
```

## Critical Rule

When you add a field to `schema.py`, add it to `schema.ts` in the **same commit**.
They must always be in sync.
