# atlassian-remote / CLAUDE.md

> Read the root `CLAUDE.md` first, especially Section 0 (deployed infrastructure).
> This package runs on the Azure VM at port 8080, exposed at `remote.ahmedxsaad.me`.

## What This Package Does

**UC3: The Forge Remote backend.**
Heavy compute that can't run in Forge's sandbox: text embedding, xqdrant vector search,
and LLM-powered RCA generation. Called exclusively by `atlassian-agent` via Forge Remote HTTP.

## Key Files

> **Layout:** standard src-layout — the importable package is `src/atlassian_remote/`,
> imported as `from atlassian_remote.vector_search import ...` (repo convention; on-disk
> path == import path keeps `mypy --strict` clean). `api.py` is at the package root, run
> with `uvicorn api:app --port 8080`. The task's `src/cf_ai_client.py` etc. map under
> `src/atlassian_remote/`.

```
atlassian-remote/
├── pyproject.toml
├── api.py                       FastAPI server (port 8080): /analyze /search /embed /health
├── src/atlassian_remote/
│   ├── config.py                env-driven config: CF models, xqdrant, Atlassian, backoff
│   ├── cf_ai_client.py          CF Workers AI calls (cf_ai_chat + cf_ai_embed); _post retries 429/5xx with backoff
│   ├── vector_search.py         xqdrant query_points (incidents + runbooks) → SearchResult
│   ├── rca_generator.py         RCA drafting via CF Workers AI → RcaDraft (+ needs_human_review)
│   ├── duplicate_resolver.py    semantic-duplicate judge via CF Workers AI → DuplicateVerdict
│   ├── analyzer.py              /analyze (record→draft→manifest→eval) + /duplicates orchestration
│   ├── recording.py             RunRecorder (binds AsyncRecordingTransport) + persist_manifest (UC2)
│   ├── eval_client.py           POST run_id to eval-engine /evaluate → EvalVerdict (best-effort)
│   ├── atlassian_client.py      Atlassian REST client with exponential backoff on 429
│   └── models.py                AnalyzeResult + DuplicateResult response envelopes (compose trace_core)
└── tests/
    ├── conftest.py              dummy env; all external calls mocked
    ├── unit/                    cf_ai_client / atlassian_client / vector_search / rca_generator / analyzer
    └── integration/             FastAPI route tests + test_full_loop (record→eval end-to-end, mocked)
```

> **No `minio_client.py` of its own.** `/search`, `/embed`, `/health` need no blob
> storage. `/analyze` *does* record cassettes to MinIO — but it does so through the
> `flight-recorder` package (a workspace dependency added in Phase 4), so boto3 is a
> transitive dep, not direct. The "MinIO Blob Storage Pattern" below is reference only.

## API Endpoints

```
POST /analyze    → { incident_key, requested_by }
                 → { run_id, rca_draft, similar, runbooks, flag_for_human, eval_verdict, replay_link }
POST /duplicates → { incident_key, requested_by } → { verdict, similar, flag_for_human }
POST /search     → { query, index, k }            → { results }
POST /embed      → { texts }                      → { embeddings }
GET  /health     → { status: "ok" }
```

> `/analyze` is the **Phase 4 end-to-end loop**: it generates a `run_id`, records every
> embed/RCA CF Workers AI call into a MinIO cassette via UC2's `AsyncRecordingTransport`
> (hash-chain audit → D1), writes a `run_manifests` row, then POSTs the `run_id` to
> eval-engine `/evaluate` and returns the `eval_verdict` + a `replay_link`. `rca_draft` is
> a `trace_core.RcaDraft`; `flag_for_human` is `confidence_score < CONFIDENCE_THRESHOLD`
> (0.70), surfaced on the envelope (**not** on the shared `RcaDraft` schema). Recording +
> eval are best-effort (an outage never fails the analysis). Internal calls use localhost
> (eval `:8000`, MinIO `:9090`); `replay_link` uses the public flight-recorder URL. All
> routes except `/health` require the `X-Sentinel-Secret` header.

> `/duplicates` searches the **incidents** collection only and judges a
> `trace_core.DuplicateVerdict`. `flag_for_human` here is stricter than `/analyze`'s:
> it trips when the verdict is not a duplicate, has no `duplicate_of` target, **or**
> `confidence < DUPLICATE_CONFIDENCE_THRESHOLD` (0.85) — so the Forge action only
> auto-links when it is safe. The flag is surfaced on the envelope, not the schema.

## LLM Pattern — CF Workers AI (NOT Anthropic SDK)

```python
# HTTP lives in cf_ai_client.py (the exact root CLAUDE.md Section 7 pattern);
# rca_generator.py just builds the prompt and validates the structured output.
from trace_core import RcaDraft
from . import cf_ai_client

async def generate_rca(incident_text, similar, runbooks) -> RcaDraft:
    messages = [
        {"role": "system", "content": RCA_SYSTEM_PROMPT},  # pins the exact JSON contract
        {"role": "user", "content": build_rca_prompt(incident_text, similar, runbooks)},
    ]
    raw = await cf_ai_client.cf_ai_chat(messages)
    return RcaDraft.model_validate_json(_extract_json(raw))  # strips ```json fences/preamble
```

## xqdrant Pattern

```python
from qdrant_client import QdrantClient

# xqdrant is at localhost:6333 — INTERNAL ONLY
client = QdrantClient(url=os.environ["XQDRANT_URL"])  # http://localhost:6333

# qdrant-client 1.18 REMOVED .search() — use query_points() (returns .points).
response = client.query_points(
    collection_name=os.environ["XQDRANT_INCIDENTS_COLLECTION"],
    query=embedding,          # a raw 768-dim vector → nearest-neighbour search
    limit=5,
    with_payload=True,
)
hits = response.points        # list[ScoredPoint]; .id / .score / .payload
```

`search_similar()` filters `score > VECTOR_SIMILARITY_THRESHOLD` (0.75) and **always**
populates `SearchResult.attribution` — from the payload's explainability block if present,
else a synthesised `Attribution` whose `confidence_margin` is the score gap to the next hit.

## MinIO Blob Storage Pattern

> Reference only — `atlassian-remote` does not currently use blob storage (no
> `minio_client.py`). This is the pattern to follow if an endpoint ever needs it; the
> flight-recorder is the package that actually talks to MinIO today.

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
  Under load it also rate-limits (429); `cf_ai_client._post` retries (429 → 30s ×3, 5xx → 5s ×2,
  via `asyncio.sleep`, warning on each) — so space real test calls >3s apart.
- xqdrant returns results even for poor matches — filter by `score > VECTOR_SIMILARITY_THRESHOLD` (0.75)
- Forge timeout is 25 seconds — keep remote calls under 15s

## Commands

```bash
make test-uc3
cd packages/atlassian-remote && uv run uvicorn api:app --reload --port 8080
curl http://localhost:8080/health
make deploy-remote
```