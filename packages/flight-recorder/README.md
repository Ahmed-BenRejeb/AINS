# flight-recorder

**UC2 — The "flight recorder" for AI agents.**
Transparently intercepts every LLM call and tool call, stores the full trace, and enables deterministic replay without touching live APIs.

---

## What Goes Here

- The LLM HTTP proxy (httpx transport override — intercepts Anthropic/OpenAI API calls)
- The MCP/tool call interceptor (decorator-based)
- Cassette read/write logic (match recorded responses by normalized step key)
- The replay engine (re-executes an agent using cassette responses instead of live APIs)
- The bisect engine (finds the first diverging step between two runs)
- Hash-chained audit record writer (tamper-evident, write-ahead logging)
- D1 and R2 storage clients (metadata and blobs)

## What Does NOT Go Here

- Evaluation logic (no graders, no verdicts) — that is `eval-engine`
- Atlassian-specific code — that is `atlassian-remote` or `atlassian-agent`
- UI or dashboard code — that is `dashboard`

## Why It Exists

When an AI agent fails in production, you cannot just re-run it — the LLM is non-deterministic, the environment has changed, and side-effecting tools (posting a comment, sending an email) may fire again. The flight recorder solves this by recording all non-deterministic boundary events so the deterministic core can re-execute identically. This package is **framework-agnostic** — it works with any Python agent, not just the UC3 Atlassian agent.

## Structure

```
flight-recorder/
├── src/
│   ├── proxy/
│   │   ├── llm_proxy.py          httpx transport override (LLM API interception)
│   │   ├── mcp_interceptor.py    decorator for tool call interception
│   │   └── cassette.py           cassette read/write + request normalization
│   ├── replay/
│   │   ├── engine.py             replay orchestrator
│   │   └── bisect.py             find first diverging step between two runs
│   ├── storage/
│   │   ├── d1_client.py          trace metadata → Cloudflare D1
│   │   └── r2_client.py          trace blobs → Cloudflare R2
│   └── audit/
│       └── hash_chain.py         write_audit_record() — hash-chained HMAC receipts
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/                 pre-recorded cassettes for deterministic tests
```

## Setup and Run

```bash
cd packages/flight-recorder
uv sync
uv run pytest tests/ -v

# Record a run
FLIGHT_MODE=record uv run python -m sentinel.flight_recorder.record --agent my_agent

# Replay it
FLIGHT_MODE=replay uv run python -m sentinel.flight_recorder.replay --run-id <uuid>

# Bisect two runs
FLIGHT_MODE=replay uv run python -m sentinel.flight_recorder.bisect --good <uuid> --bad <uuid>
```

## Key Environment Variables

| Variable | Values | Effect |
|---|---|---|
| `FLIGHT_MODE` | `record` | intercept + store everything |
| `FLIGHT_MODE` | `replay` | intercept + return cassette responses |
| `FLIGHT_MODE` | `passthrough` | do nothing (production default) |
