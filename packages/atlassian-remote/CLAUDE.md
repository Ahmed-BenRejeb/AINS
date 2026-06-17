# atlassian-remote / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**UC3: The Forge Remote backend.** Runs on the Azure VM. Handles all heavy compute that can't run inside Forge's sandbox: text embedding via Cloudflare Workers AI, vector search via Cloudflare Vectorize, and LLM reasoning via the Anthropic API (Claude). Called exclusively from `atlassian-agent` via Forge Remote HTTP.

## Key Files

```
atlassian-remote/
├── pyproject.toml
├── api.py                  ← FastAPI server — the entry point called by Forge
├── src/
│   ├── embedder.py         ← embed text via Workers AI (@cf/baai/bge-base-en-v1.5)
│   ├── vector_search.py    ← Cloudflare Vectorize queries (incidents + runbooks indexes)
│   ├── rca_generator.py    ← Claude-powered RCA drafting + structured output
│   ├── anthropic_client.py ← shared Anthropic SDK client (handles rate limiting + logging)
│   └── atlassian_client.py ← Atlassian REST client with backoff (used for data fetching)
└── tests/
    ├── unit/
    │   ├── test_embedder.py       ← mocks Workers AI call
    │   ├── test_vector_search.py  ← mocks Vectorize API
    │   └── test_rca_generator.py  ← mocks Anthropic API
    ├── integration/
    │   └── test_api_endpoints.py  ← tests the FastAPI routes with mocked dependencies
    └── fixtures/
        ├── sample_incident.json
        ├── sample_similar_incidents.json
        └── sample_runbooks.json
```

## API Endpoints

```
POST /analyze
    Input:  { incident: NormalizedIncident, requested_by: str (accountId) }
    Output: { rca_draft: RcaDraft, similar_incidents: list, runbooks: list }

POST /search
    Input:  { query: str, index: "incidents" | "runbooks", k: int }
    Output: { results: list[SearchResult] }

POST /embed
    Input:  { texts: list[str] }
    Output: { embeddings: list[list[float]] }

GET  /health
    Output: { status: "ok", version: str }
```

## Request Authentication

Every request from Forge must include:
```python
# api.py — verify on every request
from fastapi import Request, HTTPException

async def verify_sentinel_secret(request: Request):
    secret = request.headers.get("X-Sentinel-Secret")
    if secret != os.environ["FORGE_REMOTE_SECRET"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # also log the accountId for audit trail
    account_id = request.headers.get("X-Account-Id", "unknown")
    logger.info(f"Request from accountId={account_id}")
```

## Embedder Pattern

```python
# src/embedder.py
# Workers AI model: @cf/baai/bge-base-en-v1.5 → 768-dim vectors

import httpx

CF_EMBED_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}"
    f"/ai/run/@cf/baai/bge-base-en-v1.5"
)

async def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed texts using Cloudflare Workers AI (BGE-Base-EN-v1.5, 768 dims).
    Free tier: 10,000 neurons/day. Resets at 00:00 UTC.
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            CF_EMBED_URL,
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            json={"text": texts}
        )
        r.raise_for_status()
        return r.json()["result"]["data"]
```

## RCA Generator Pattern

```python
# src/rca_generator.py
# Always use structured output (Pydantic) — required for downstream eval

class RcaDraft(BaseModel):
    root_cause_hypothesis: str
    evidence: list[str]        # specific runbook sections + past incident keys cited
    severity_rationale: str
    proposed_severity: Literal["P1", "P2", "P3", "P4"]
    proposed_assignee_team: str
    duplicate_check: DuplicateCheck
    knowledge_gaps: list[str]
    confidence_score: float     # 0.0–1.0; below CONFIDENCE_THRESHOLD → flag_for_human

async def generate_rca(
    incident: NormalizedIncident,
    similar_incidents: list[SearchResult],
    runbooks: list[SearchResult],
) -> RcaDraft:
    """Generate a structured RCA draft using Claude."""
    # Always structured output — never free text
    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=RCA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_rca_prompt(incident, similar_incidents, runbooks)}],
    )
    # Parse with Pydantic
    return RcaDraft.model_validate_json(response.content[0].text)
```

## Critical Rules for This Package

- **All Anthropic API calls go through `anthropic_client.py`.** Never instantiate `Anthropic()` directly elsewhere. The shared client handles rate limiting, logging to Langfuse, and error handling.
- **All LLM outputs use structured Pydantic models.** Never let Claude return free text that you then parse with regex or `str.split()`.
- **Log every RCA request to Langfuse** via `anthropic_client.py` (OpenLLMetry auto-instruments this). Every request must be traceable.
- **Tests must mock external calls.** Use `pytest-httpx` for Workers AI and Vectorize. Use `anthropic.helpers.make_message()` for mocking Claude responses. No live API calls in tests.

## Known Gotchas

- **Workers AI free tier is 10,000 neurons/day**, reset at 00:00 UTC. During the demo, batch embedding calls to avoid hitting the limit. Don't embed one at a time in a loop.
- **Vectorize returns results even for poor matches.** Always filter by `score > VECTOR_SIMILARITY_THRESHOLD` (default: 0.75 in constants). Without this, the RCA cites irrelevant runbooks.
- **Claude's `max_tokens` must be set.** Structured output prompts that request JSON need enough headroom. Use `max_tokens=1000` for RCA drafts.

## Commands

```bash
make test-uc3
cd packages/atlassian-remote && uv run uvicorn api:app --reload --port 8080
curl -X POST http://localhost:8080/health
make deploy-remote
```
