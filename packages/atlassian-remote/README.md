# atlassian-remote

**UC3 — The heavy compute backend.**
Everything that the Forge sandbox cannot run: text embedding, vector search, and CF Workers AI–powered RCA generation. Called exclusively by `atlassian-agent` via Forge Remote HTTP.

---

## What Goes Here

- FastAPI server exposing `/analyze`, `/duplicates`, `/search`, `/embed`, `/health` endpoints
- Text embedder (`@cf/baai/bge-base-en-v1.5` via Cloudflare Workers AI)
- Vector search client (xqdrant at `localhost:6333` — incidents + runbooks collections)
- RCA generator (CF Workers AI `@cf/meta/llama-3.1-8b-instruct-fp8-fast`, structured Pydantic output)
- Semantic duplicate resolver (`duplicate_resolver.py` — CF Workers AI judges whether an incident duplicates a past one → `DuplicateVerdict`)
- Shared CF Workers AI client (`cf_ai_client.py` — chat + embed; retries 429/5xx with backoff)
- Shared Atlassian REST client (with exponential backoff for 429s)
- The Phase 4 loop glue: records each `/analyze` run with UC2 (`recording.py`) and hands the `run_id` to UC1 for judging (`eval_client.py`)

## What Does NOT Go Here

- Forge/Atlassian SDK code — that is `atlassian-agent` (TypeScript, Forge sandbox)
- Trace capture — that is `flight-recorder`
- Verdict production — that is `eval-engine`
- A MinIO client of its own — `/analyze` *does* write cassettes to MinIO, but it does so through the `flight-recorder` package (a workspace dependency), not a local `minio_client.py`

## Why It Exists (and Why It's Separate from `atlassian-agent`)

The Forge sandbox has a 25-second timeout, no GPU, and limited memory. Embedding 100 incident descriptions or making a large LLM call cannot happen inside Forge. This package runs on the Azure VM and is reachable via Cloudflare Tunnel. It is also separate from `eval-engine` because its job is *generation* (produce an RCA draft) while `eval-engine`'s job is *evaluation* (score a trace). These are distinct responsibilities with different inputs and outputs.

## Structure

```
atlassian-remote/
├── pyproject.toml
├── api.py                       FastAPI entry point (port 8080)
├── src/atlassian_remote/        importable package — `from atlassian_remote.… import …`
│   ├── config.py                env-driven config (CF + xqdrant + Atlassian + backoff)
│   ├── cf_ai_client.py          CF Workers AI calls (chat + embed)
│   ├── vector_search.py         xqdrant queries (localhost:6333, internal only)
│   ├── rca_generator.py         CF Workers AI RCA drafting (structured RcaDraft output)
│   ├── duplicate_resolver.py    semantic-duplicate judge via CF Workers AI → DuplicateVerdict
│   ├── analyzer.py              /analyze loop (record→draft→manifest→eval) + /duplicates resolution
│   ├── recording.py             RunRecorder (UC2 AsyncRecordingTransport) + run-manifest write
│   ├── eval_client.py           POST run_id → eval-engine /evaluate → EvalVerdict (best-effort)
│   ├── atlassian_client.py      Atlassian REST client with 429 backoff
│   └── models.py                AnalyzeResult (+ run_id/eval_verdict/replay_link) + DuplicateResult envelopes
└── tests/
    ├── conftest.py              dummy env; all external calls mocked (pytest-httpx)
    ├── unit/                    cf_ai_client / atlassian_client / vector_search / rca_generator / duplicate_resolver / analyzer
    └── integration/             FastAPI route tests + test_full_loop (record→eval, all mocked)
```

## Setup and Run

```bash
cd packages/atlassian-remote
uv sync
uv run pytest tests/ -v
uv run uvicorn api:app --reload --port 8080

# Health check
curl http://localhost:8080/health
```

## Security: Every Request Must Be Authenticated

Every request from the Forge app includes `X-Sentinel-Secret` and `X-Account-Id` headers.
The API verifies both on every request. Never bypass this check in production.

## All LLM Outputs Must Use Pydantic Models

```python
# Import the canonical model from trace-core — never redefine it locally.
from trace_core import RcaDraft

# RcaDraft fields: root_cause_hypothesis, evidence, proposed_severity (SeverityLevel),
# confidence_score, proposed_assignee_team, duplicate_check, knowledge_gaps, ...
raw = await cf_ai_client.cf_ai_chat(messages)
return RcaDraft.model_validate_json(_extract_json(raw))  # strips ```json fences
```

Never let the LLM return free text and parse it with regex. Structured output is required for the downstream eval engine to score the RCA consistently.
