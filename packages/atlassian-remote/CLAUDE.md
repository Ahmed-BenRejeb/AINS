# atlassian-remote / CLAUDE.md

> Read the root `CLAUDE.md` first, especially Section 0 (deployed infrastructure).
> This package runs on the Azure VM at port 8080, exposed at `remote.ahmedxsaad.me`.

## What This Package Does

**UC3: The Forge Remote backend.**
Heavy compute that can't run in Forge's sandbox: text embedding, xqdrant vector search,
and LLM-powered RCA generation. Called exclusively by `atlassian-agent` via Forge Remote HTTP.

## Key Files

```
atlassian-remote/
├── pyproject.toml
├── api.py                    FastAPI server — entry point
├── src/
│   ├── cf_ai_client.py       CF Workers AI calls (embed, chat, safety filter)
│   ├── vector_search.py      xqdrant client (search incidents + runbooks)
│   ├── rca_generator.py      RCA drafting via CF Workers AI (structured Pydantic output)
│   ├── atlassian_client.py   Atlassian REST client with exponential backoff
│   └── minio_client.py       S3-compatible blob storage via MinIO
└── tests/
    ├── unit/                 all external calls mocked (pytest-httpx)
    ├── integration/
    └── fixtures/
```

## API Endpoints

```
POST /analyze   → { incident, requested_by } → { rca_draft, similar, runbooks }
POST /search    → { query, index, k }         → { results }
POST /embed     → { texts }                   → { embeddings }
GET  /health    → { status: "ok" }
```

## LLM Pattern — CF Workers AI (NOT Anthropic SDK)

```python
# All LLM calls use this pattern — see root CLAUDE.md Section 7
import httpx, os

CF_AI_URL = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/ai/run"

async def generate_rca(incident, similar, runbooks) -> RcaDraft:
    messages = [
        {"role": "system", "content": RCA_SYSTEM_PROMPT},
        {"role": "user", "content": build_rca_prompt(incident, similar, runbooks)}
    ]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{CF_AI_URL}/{os.environ['CF_AI_MODEL_MAIN']}",
            headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
            json={"messages": messages, "max_tokens": 1000},
            timeout=30.0,
        )
        r.raise_for_status()
        raw = r.json()["result"]["response"]
    return RcaDraft.model_validate_json(raw)
```

## xqdrant Pattern

```python
from qdrant_client import QdrantClient
from qdrant_client.models import SearchParams

# xqdrant is at localhost:6333 — INTERNAL ONLY
client = QdrantClient(url=os.environ["XQDRANT_URL"])  # http://localhost:6333

results = client.search(
    collection_name=os.environ["XQDRANT_INCIDENTS_COLLECTION"],
    query_vector=embedding,
    limit=5,
    with_payload=True,
)
```

## MinIO Blob Storage Pattern

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["BLOB_STORAGE_ENDPOINT"],      # http://localhost:9090
    aws_access_key_id=os.environ["BLOB_STORAGE_ACCESS_KEY"],    # minio
    aws_secret_access_key=os.environ["BLOB_STORAGE_SECRET_KEY"], # miniosecret
)
bucket = os.environ["BLOB_STORAGE_BUCKET"]  # sentinel-cassettes
```

## Security: Verify Every Request

```python
async def verify_request(request: Request):
    secret = request.headers.get("X-Sentinel-Secret")
    if secret != os.environ["FORGE_REMOTE_SECRET"]:
        raise HTTPException(status_code=401)
    account_id = request.headers.get("X-Account-Id", "unknown")
    logger.info(f"request from accountId={account_id}")
```

## Critical Rules

- **All LLM calls go through CF Workers AI** — never Anthropic SDK, never OpenAI SDK
- **Blob storage is MinIO** — use boto3 with `endpoint_url=http://localhost:9090`
- **xqdrant is at localhost:6333** — internal only, never exposed
- **All LLM outputs must be Pydantic models** — never free text
- **Attribution from xqdrant MUST be propagated** — never discard it

## Known Gotchas

- CF Workers AI free tier: 10,000 neurons/day, resets at 00:00 UTC. Batch embedding calls.
- xqdrant returns results even for poor matches — filter by `score > VECTOR_SIMILARITY_THRESHOLD` (0.75)
- Forge timeout is 25 seconds — keep remote calls under 15s

## Commands

```bash
make test-uc3
cd packages/atlassian-remote && uv run uvicorn api:app --reload --port 8080
curl http://localhost:8080/health
make deploy-remote
```