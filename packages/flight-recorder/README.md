# flight-recorder

**UC2 — The "flight recorder" for AI agents.**
Transparently intercepts every LLM call and tool call, stores the full trace, and enables deterministic replay without touching live APIs.

---

## What Goes Here

- The LLM HTTP proxy (httpx transport override — intercepts **Cloudflare Workers AI** calls)
- The MCP/tool call interceptor (decorator-based)
- Cassette read/write logic (match recorded responses by normalized step key)
- The replay engine (re-executes an agent using cassette responses instead of live APIs)
- The bisect engine (finds the first diverging step between two runs)
- Hash-chained audit record writer (tamper-evident, write-ahead logging)
- D1 and **MinIO** storage clients (trace metadata and cassette blobs — MinIO, not R2)

## What Does NOT Go Here

- Evaluation logic (no graders, no verdicts) — that is `eval-engine`
- Atlassian-specific code — that is `atlassian-remote` or `atlassian-agent`
- UI or dashboard code — that is `dashboard`

## Why It Exists

When an AI agent fails in production, you cannot just re-run it — the LLM is non-deterministic, the environment has changed, and side-effecting tools (posting a comment, sending an email) may fire again. The flight recorder solves this by recording all non-deterministic boundary events so the deterministic core can re-execute identically. This package is **framework-agnostic** — it works with any Python agent, not just the UC3 Atlassian agent.

## Structure

Standard src-layout: the importable package is `src/flight_recorder/`
(`from flight_recorder.proxy.cassette import ...`); `api.py` is at the package root.

```
flight-recorder/
├── api.py                       FastAPI server (port 8001): /runs /replay /bisect /health
├── src/flight_recorder/
│   ├── config.py                FLIGHT_MODE resolution, CF-URL detection, genesis hash
│   ├── exceptions.py            CassetteMissError (replay never falls back to a live call)
│   ├── proxy/
│   │   ├── llm_proxy.py          RecordingTransport — httpx override, intercepts CF AI calls
│   │   ├── mcp_interceptor.py    @record_tool decorator for tool call interception
│   │   └── cassette.py           cassette read/write + request normalization
│   ├── replay/
│   │   ├── engine.py             replay orchestrator (asserts zero live calls)
│   │   └── bisect.py             find first diverging step between two runs
│   ├── storage/
│   │   ├── d1_client.py          trace metadata → Cloudflare D1
│   │   └── minio_client.py       cassette blobs → MinIO (S3-compatible, NOT R2)
│   └── audit/
│       └── hash_chain.py         write_audit_record() — hash-chained HMAC receipts
└── tests/                        cassette / llm_proxy / hash_chain / replay / mcp / bisect
```

## Setup and Run

```bash
make test-uc2                                   # pytest + coverage (from repo root)
cd packages/flight-recorder
FLIGHT_MODE=replay uv run uvicorn api:app --port 8001   # serve /runs, /replay, /bisect
```

```python
# Record a run, then replay it with zero live API calls
import httpx
from flight_recorder import RecordingTransport, replay_run

client = httpx.Client(transport=RecordingTransport(run_id, mode="record"))
agent(client)                       # every CF Workers AI call is taped into the cassette
result = replay_run(run_id, agent)  # re-runs against the cassette
assert result.live_call_count == 0
```

## Key Environment Variables

| Variable | Values | Effect |
|---|---|---|
| `FLIGHT_MODE` | `record` | intercept + store everything |
| `FLIGHT_MODE` | `replay` | intercept + return cassette responses |
| `FLIGHT_MODE` | `passthrough` | do nothing (production default) |
