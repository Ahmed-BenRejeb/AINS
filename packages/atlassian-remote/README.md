# atlassian-remote

**UC3 — The heavy compute backend.**
Everything that the Forge sandbox cannot run: text embedding, vector search, and Claude-powered RCA generation. Called exclusively by `atlassian-agent` via Forge Remote HTTP.

---

## What Goes Here

- FastAPI server exposing `/analyze`, `/search`, `/embed`, `/health` endpoints
- Text embedder (`@cf/baai/bge-base-en-v1.5` via Cloudflare Workers AI)
- Vector search client (Cloudflare Vectorize — incidents + runbooks indexes)
- RCA generator (Claude via Anthropic API, structured Pydantic output)
- Shared Anthropic client (rate limiting + Langfuse logging)
- Shared Atlassian REST client (with exponential backoff for 429s)

## What Does NOT Go Here

- Forge/Atlassian SDK code — that is `atlassian-agent` (TypeScript, Forge sandbox)
- Trace capture — that is `flight-recorder`
- Verdict production — that is `eval-engine`

## Why It Exists (and Why It's Separate from `atlassian-agent`)

The Forge sandbox has a 25-second timeout, no GPU, and limited memory. Embedding 100 incident descriptions or making a large LLM call cannot happen inside Forge. This package runs on the Azure VM and is reachable via Cloudflare Tunnel. It is also separate from `eval-engine` because its job is *generation* (produce an RCA draft) while `eval-engine`'s job is *evaluation* (score a trace). These are distinct responsibilities with different inputs and outputs.

## Structure

```
atlassian-remote/
├── pyproject.toml
├── api.py                   FastAPI entry point
├── src/
│   ├── embedder.py          Workers AI embedding calls
│   ├── vector_search.py     Cloudflare Vectorize queries
│   ├── rca_generator.py     Claude RCA drafting (structured Pydantic output)
│   ├── anthropic_client.py  shared Anthropic client (rate limit + Langfuse logging)
│   └── atlassian_client.py  Atlassian REST client with backoff
└── tests/
    ├── unit/                all external calls mocked (pytest-httpx)
    ├── integration/         FastAPI route tests with mocked dependencies
    └── fixtures/            sample incidents, similar incidents, runbooks
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
class RcaDraft(BaseModel):
    root_cause_hypothesis: str
    evidence: list[str]
    proposed_severity: Literal["P1", "P2", "P3", "P4"]
    confidence_score: float
    ...
```

Never let Claude return free text and parse it with regex. Structured output is required for the downstream eval engine to score the RCA consistently.
