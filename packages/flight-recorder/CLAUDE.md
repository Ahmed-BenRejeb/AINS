# flight-recorder / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**UC2: The "flight recorder" for AI agents.** Transparently intercepts every LLM API call and tool call during a live agent run, stores the full input/output/metadata, and enables deterministic replay without touching live APIs.

## Key Files

```
flight-recorder/
├── src/
│   ├── proxy/
│   │   ├── llm_proxy.py         ← httpx transport override (intercepts Anthropic/OpenAI calls)
│   │   ├── mcp_interceptor.py   ← decorator-based tool call interceptor
│   │   └── cassette.py          ← cassette read/write + step key normalization
│   ├── replay/
│   │   ├── engine.py            ← replay orchestrator (loads cassette, re-executes agent)
│   │   └── bisect.py            ← finds first diverging step between two runs
│   ├── storage/
│   │   ├── d1_client.py         ← D1 (metadata, step index, run manifests)
│   │   └── r2_client.py         ← R2 (full blobs: prompts, responses, state snapshots)
│   └── audit/
│       └── hash_chain.py        ← write_audit_record() — hash-chained, HMAC-signed receipts
└── tests/
    ├── unit/
    │   ├── test_llm_proxy.py
    │   ├── test_cassette.py
    │   └── test_bisect.py
    ├── integration/
    │   └── test_record_replay.py  ← records a real agent run, replays it, asserts zero live calls
    └── fixtures/
        ├── sample_run_record/     ← pre-recorded cassette for a synthetic agent run
        └── mock_agent.py          ← minimal agent used in tests
```

## The Two Interception Layers

### Layer 1: LLM HTTP Proxy (httpx transport override)
```python
# Usage — inject into any Anthropic SDK client:
from sentinel.flight_recorder.proxy.llm_proxy import RecordingTransport
from anthropic import Anthropic
import httpx

transport = RecordingTransport(run_id="abc123", mode="record")  # or "replay"
client = Anthropic(http_client=httpx.Client(transport=transport))
# All calls through this client are now recorded/replayed
```

### Layer 2: Tool Interceptor (decorator)
```python
from sentinel.flight_recorder.proxy.mcp_interceptor import record_tool

@record_tool(run_id=current_run_id, mode=FLIGHT_MODE)
def create_jira_issue(summary: str, description: str) -> dict:
    # real implementation
```

## Critical Rules for This Package

- **FLIGHT_MODE env var controls behavior.** `record` = intercept + store. `replay` = intercept + inject from cassette. `passthrough` = do nothing. Never hardcode the mode.
- **Step key normalization is critical.** The cassette lookup key is `hash_step_key(request)` from `trace-core`. It strips ephemeral values (timestamps, request IDs) before hashing. If replay gives a cassette miss when it shouldn't, debug `cassette.py:normalize_request()` first.
- **Audit records are written BEFORE the actual call.** This is write-ahead logging — if the call crashes, the audit trail still exists.
- **Tests must mock live API calls.** Never make real Anthropic/Atlassian API calls in unit or integration tests. Use `pytest-httpx` to mock HTTP.

## Known Gotchas

- **Timestamps and UUIDs in prompts cause cassette misses.** If you generate `datetime.now()` or `uuid4()` inside a prompt, the hash changes every run. Stabilize these with fixture-injected constants during tests. See `tests/fixtures/mock_agent.py` for the pattern.
- **Cassette format versioned by `CASSETTE_VERSION`.** Changing `normalize_request()` in `trace-core` bumps this. Old cassettes are incompatible — re-record them.

## Commands

```bash
make test-uc2
FLIGHT_MODE=record uv run python -m sentinel.flight_recorder.record --agent my_agent
FLIGHT_MODE=replay uv run python -m sentinel.flight_recorder.replay --run-id <run_id>
FLIGHT_MODE=replay uv run python -m sentinel.flight_recorder.bisect --good <run_id> --bad <run_id>
```
