# CLAUDE.md — Sentinel: AI Agent Reliability Platform
### ⚠️ READ THIS FILE AT THE START OF EVERY SESSION — NO EXCEPTIONS

> This file is the single source of truth for project context, architecture, and working rules.
> **Update it whenever architecture changes, a gotcha is discovered, or a phase completes.**
> Codex will evaluate your work after each session — write code as if you won't be there to explain it.
>
> **📝 Update log rule (required, no exceptions):** every time you edit this file, update the
> **_Last updated_** line at the very bottom with the **exact timestamp** (`YYYY-MM-DD HH:MM TZ`),
> **the name of who/what made the change** (person or agent), and a one-line summary of what changed.
> (`AGENTS.md` is a **symlink** to this file, so it stays in sync automatically — never edit it separately.)

---

## 0. DEPLOYED INFRASTRUCTURE (read this first)

Everything below is live and running. Use these exact values — do not invent new ones.

### Azure VM
- **IP:** `48.220.48.34`
- **User:** `Fantazy`
- **SSH:** `ssh Fantazy@48.220.48.34`
- **OS:** Ubuntu 24.04 LTS

### Live Service URLs
| Service | URL | Internal Port |
|---|---|---|
| Langfuse (trace UI) | `https://langfuse.ahmedxsaad.me` | 3000 |
| Eval Engine API | `https://eval.ahmedxsaad.me` | 8000 |
| Forge Remote API | `https://remote.ahmedxsaad.me` | 8080 |
| Flight Recorder API | `https://flight.ahmedxsaad.me` | 8001 |
| Dashboard (UI) | `https://dashboard.ahmedxsaad.me` | 3001 |
| xqdrant | internal only | 6333 |
| MinIO S3 | internal only | 9090 |

> All public hostnames sit behind a Cloudflare **managed/bot challenge** (the zone
> default) — browsers pass it (sometimes after a one-time "checking your browser"
> interstitial); `curl`/bots get a `403 cf-mitigated: challenge`. That 403 from a
> shell is expected and does **not** mean the service is down. Each hostname is an
> ingress rule in the `sentinel` tunnel's `~/.cloudflared/config.yml` on the VM
> (run via the `cloudflared` systemd unit). The dashboard itself runs as the
> `sentinel-dashboard` systemd unit (`next start -p 3001`).
>
> The 3 Python services run as systemd units — **`sentinel-eval`** (:8000),
> **`sentinel-remote`** (:8080), **`sentinel-flight`** (:8001) — each
> `uv run uvicorn api:app --app-dir packages/<pkg>` with
> `WorkingDirectory=/home/Fantazy/AINS` and `EnvironmentFile=/srv/sentinel/.env`
> (`Restart=always`, enabled on boot; logs append to `/srv/sentinel/logs/<pkg>.log`).
> Manage with `sudo systemctl {status,restart} sentinel-{eval,remote,flight}`.
> Defined in `infra/azure/setup.sh`.

### Cloudflare Resources
| Resource | Name / ID |
|---|---|
| D1 database | `sentinel-traces` (ID in `/srv/sentinel/.env`) |
| Vectorize index | `sentinel-embeddings` (768-dim, cosine) |
| Workers AI | `@cf/meta/llama-3.1-8b-instruct-fp8-fast` (main LLM — RCA + judge; ~6x cheaper/neuron than llama-3.3-70b, clean JSON) |
| Workers AI | `@cf/meta/llama-guard-3-8b` (safety filter) |
| Workers AI | `@cf/baai/bge-base-en-v1.5` (embeddings) |

### Atlassian (ahmedains.atlassian.net)
| Field | Value |
|---|---|
| Site URL | `https://ahmedains.atlassian.net` |
| Jira project key | `AO` (JSM project — has Incident issue type) |
| JSM Service desk ID | `1` |
| Incident issue type ID | `10013` (use ID, NOT name — name is `[System] Incident`) |
| Confluence space | `SENT` |
| Incidents seeded | 100 (10 root-cause categories × 10 variants) |
| Runbooks seeded | 10 (one per root-cause category) |

### Blob Storage (MinIO — NOT Cloudflare R2)
> R2 was skipped — requires credit card. MinIO runs inside the Langfuse Docker stack.
- Endpoint: `http://localhost:9090`
- Bucket: `sentinel-cassettes`
- Access key: `minio` / Secret key: `<see /srv/sentinel/.env>`
- S3-compatible — use boto3 with endpoint_url

### xqdrant
> Running standard Qdrant image as placeholder. Swap image for `fantazytv/xqdrant` when fork is ready.
- URL: `http://localhost:6333`
- Collections: `incidents` (768-dim), `runbooks` (768-dim)
- Port 6333 is internal ONLY — never expose via Cloudflare Tunnel

### GitHub
- Repo: `https://github.com/ahmedxsaad/AINS`
- Team: Ahmed Saad (ahmedxsaad), Moetez Fradi, Ahmed Ben Rejeb

---

## 1. Project Identity

**Name:** Sentinel
**Mission:** A unified AI agent reliability platform for the Atlassian ecosystem.
**Hackathon:** AINS Hackathon 2026, organised by AINS 4.0 × Vectors (covectors.io)

**The three use cases we solve — as one system:**
- **UC2 (Flight Recorder)** → captures every LLM call and tool call into OTel GenAI traces
- **UC1 (Eval Engine)** → judges those traces, produces auditable verdicts with failure attribution
- **UC3 (Atlassian Agent)** → a real Rovo Agent on Forge that gets instrumented by UC1+UC2; verdicts land as Jira issues

**The narrative:** *"We built the reliability infrastructure a Marketplace AI vendor needs, and dogfooded it on a real Atlassian agent."*

Reference documents:
- Full technical battle plan: `docs/BATTLE_PLAN.md`
- Architecture diagram: `docs/ARCHITECTURE.md`
- OTel extension spec: `spec/otel-genai-replay-extension.md`
- MCP audit spec: `spec/mcp-audit-trail-proposal.md`

---

## 2. Monorepo Structure

```
AINS/
├── CLAUDE.md                  ← YOU ARE HERE — read first every session
├── AGENTS.md                  ← symlink → CLAUDE.md (single source of truth; Codex/other agents read this)
├── Makefile                   ← all commands live here, use make <cmd>
├── .env.example               ← copy to .env, never commit .env
│
├── packages/
│   ├── trace-core/            ← shared OTel GenAI schema + types (Python + TS)
│   ├── flight-recorder/       ← UC2: HTTP proxy, record/replay/bisect/inject (Python)
│   ├── eval-engine/           ← UC1: graders, judge, drift, verdicts (Python)
│   ├── atlassian-agent/       ← UC3: Forge app — Rovo Agent + actions (TypeScript)
│   ├── atlassian-remote/      ← UC3: heavy compute backend via Forge Remote (Python)
│   └── dashboard/             ← shared UI: traces, verdicts, replay (Next.js)
│
├── infra/
│   ├── cloudflare/wrangler.toml
│   └── azure/setup.sh
│
├── scripts/
│   ├── seed_atlassian.py      ← ALREADY RUN — 100 incidents + 10 runbooks seeded
│   └── run_synthetic_eval.py
│
├── spec/                      ← open contribution artifacts (bonus points)
└── docs/
```

### File Structure Rules — ENFORCED
- ✅ New modules go in their designated package directory
- ✅ Shared types/schemas go in `packages/trace-core/` — never duplicate them
- ❌ Never create files at the root level unless they are config files
- ❌ Never hardcode values that belong in `.env`

---

## 3. Environment Variables

The `.env` file lives at `/srv/sentinel/.env` on the VM (chmod 600 — only Fantazy can read it).
For local dev, copy `.env.example` to `.env` and fill in values.

```bash
# ── Cloudflare Workers AI (replaces Anthropic — no API key needed beyond CF token) ──
CLOUDFLARE_ACCOUNT_ID=<see /srv/sentinel/.env>
CLOUDFLARE_API_TOKEN=<in /srv/sentinel/.env>

# Optional: route ONLY Workers AI to a separate account (e.g. a teammate's) for a
# fresh 10k-neuron/day budget. When set, cf_ai_client uses these; D1/MinIO stay on
# CLOUDFLARE_* (D1 reads them directly), so the trace store is unaffected. Unset → CLOUDFLARE_*.
CF_AI_ACCOUNT_ID=
CF_AI_API_TOKEN=

CF_AI_MODEL_MAIN=@cf/meta/llama-3.1-8b-instruct-fp8-fast
CF_AI_MODEL_SAFETY=@cf/meta/llama-guard-3-8b
CF_AI_MODEL_EMBED=@cf/baai/bge-base-en-v1.5

# ── Cloudflare D1 ─────────────────────────────────────────────────────────────
CF_D1_DATABASE_ID=<see /srv/sentinel/.env>

# ── Cloudflare Vectorize ──────────────────────────────────────────────────────
CF_VECTORIZE_INDEX=sentinel-embeddings

# ── Atlassian ─────────────────────────────────────────────────────────────────
ATLASSIAN_SITE=https://ahmedains.atlassian.net
ATLASSIAN_JIRA_PROJECT_KEY=AO
ATLASSIAN_JSM_SERVICE_DESK_ID=1

# ── Langfuse ──────────────────────────────────────────────────────────────────
LANGFUSE_HOST=https://langfuse.ahmedxsaad.me
LANGFUSE_HOST_INTERNAL=http://127.0.0.1:3000   # SDK delivery target (bypasses CF challenge; see §10)
LANGFUSE_PUBLIC_KEY=<see /srv/sentinel/.env>
LANGFUSE_SECRET_KEY=<in /srv/sentinel/.env>

# ── Blob Storage (MinIO — S3-compatible) ─────────────────────────────────────
BLOB_STORAGE_ENDPOINT=http://localhost:9090
BLOB_STORAGE_BUCKET=sentinel-cassettes
BLOB_STORAGE_ACCESS_KEY=<see /srv/sentinel/.env>
BLOB_STORAGE_SECRET_KEY=<see /srv/sentinel/.env>
BLOB_STORAGE_USE_SSL=false

# ── xqdrant ───────────────────────────────────────────────────────────────────
XQDRANT_URL=http://localhost:6333
XQDRANT_INCIDENTS_COLLECTION=incidents
XQDRANT_RUNBOOKS_COLLECTION=runbooks

# ── Flight Recorder ───────────────────────────────────────────────────────────
FLIGHT_MODE=record    # record | replay | passthrough
AUDIT_HMAC_KEY=<in /srv/sentinel/.env>

# ── Eval Engine ───────────────────────────────────────────────────────────────
EVAL_CONFIDENCE_THRESHOLD=0.70
VECTOR_SIMILARITY_THRESHOLD=0.75

# ── Forge Remote ──────────────────────────────────────────────────────────────
FORGE_REMOTE_URL=https://remote.ahmedxsaad.me
FORGE_REMOTE_SECRET=<in /srv/sentinel/.env>

# ── OTel ──────────────────────────────────────────────────────────────────────
OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

---

## 4. Commands (always use `make`, never remember raw commands)

```bash
make setup          # install all dependencies (Python + Node)
make test           # run ALL tests across all packages
make test-uc1       # eval-engine tests only
make test-uc2       # flight-recorder tests only
make test-uc3       # atlassian-remote + atlassian-agent tests only
make check          # check-docs + lint + typecheck (run before every commit)
make check-docs      # .env.example parity with code + no doc drift markers
make lint           # ruff (Python) + eslint (TypeScript)
make format         # black + isort (Python), prettier (TypeScript)
make eval           # run eval suite, output pass^k report
make seed-xqdrant   # embed AO incidents + SENT runbooks (BGE-768) into xqdrant
make deploy-forge   # deploy Forge app to Atlassian
make deploy-remote  # deploy atlassian-remote to Azure VM
```

---

## 5. Tech Stack (ACTUAL — reflects what is deployed)

### Models — Cloudflare Workers AI (NO Anthropic API key)
All LLM calls go through:
```python
# POST https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}
# Authorization: Bearer {CLOUDFLARE_API_TOKEN}
# Content-Type: application/json
# Body: {"messages": [...], "max_tokens": 1000}
```

| Use | Model | Notes |
|---|---|---|
| Main LLM (RCA, eval judge) | `@cf/meta/llama-3.1-8b-instruct-fp8-fast` | 4,119/34,868 neurons per M in/out — ~6x cheaper than llama-3.3-70b (was the default), clean JSON, fast for Forge 25s; stretches the free 10k/day |
| Safety pre-filter | `@cf/meta/llama-guard-3-8b` | Fast, cheap |
| Embeddings (768-dim) | `@cf/baai/bge-base-en-v1.5` | For xqdrant + drift |

### Frameworks
| Layer | Choice |
|---|---|
| Agent framework | LangGraph |
| LLM instrumentation | OpenLLMetry (`traceloop-sdk`) |
| Observability UI | Langfuse (self-hosted, running) — the 3 Python services trace every LLM call / vector search via the Langfuse **v4** SDK (`<pkg>/langfuse_client.py`) |
| Forge app (UC3) | Forge TypeScript SDK |
| LLM proxy/intercept | httpx transport override |
| Vector search | xqdrant (Qdrant fork, port 6333) |
| Blob storage | MinIO (S3-compatible, port 9090) — NOT Cloudflare R2 |
| Trace metadata | Cloudflare D1 (SQLite) |
| Dashboard | Next.js 16 + shadcn-style UI |

### Language Split
| Area | Language |
|---|---|
| Forge app (UC3) | TypeScript (mandatory for Forge) |
| Eval engine (UC1) | Python |
| Flight recorder (UC2) | Python |
| atlassian-remote backend | Python |
| Dashboard | TypeScript (Next.js) |

---

## 6. Coding Standards

### Python
```python
# ✅ Required: type hints on all function signatures
def evaluate_run(run_id: str, k: int = 8) -> EvalVerdict:

# ✅ Required: docstrings on every function
def evaluate_run(run_id: str, k: int = 8) -> EvalVerdict:
    """
    Evaluate a single agent run at multiple levels.
    Args:
        run_id: UUID of the recorded run.
        k: Number of independent trials for pass^k.
    Returns:
        EvalVerdict with scores, failure attribution, self-evaluation.
    """

# ✅ Required: Pydantic models for all data structures
# ✅ Required: named constants, never magic numbers
CONFIDENCE_THRESHOLD = 0.70
PASS_AT_K_TRIALS = 8
```

**Tooling:** `ruff` (lint), `black` (format), `isort` (imports), `mypy` (types), `pytest` (tests)

### TypeScript
```typescript
// ✅ Required: strict TypeScript, no `any`
// ✅ Required: JSDoc on all exported functions
// tsconfig.json must have "strict": true
```

### Universal Rules
- No `TODO` or `FIXME` in commits to `main`
- No hardcoded URLs, tokens, or IDs — everything in `.env`
- No `console.log` in production code — use structured logger
- No commented-out code — delete it, git history preserves it

---

## 7. CF Workers AI — How to Call It

**This is the standard pattern for ALL LLM calls in this project (no Anthropic SDK):**

```python
import httpx, os

CF_ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"]
CF_API_TOKEN  = os.environ["CLOUDFLARE_API_TOKEN"]
CF_AI_URL     = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run"

async def cf_ai_chat(model: str, messages: list[dict], max_tokens: int = 1000) -> str:
    """Call Cloudflare Workers AI chat completion endpoint."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{CF_AI_URL}/{model}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            json={"messages": messages, "max_tokens": max_tokens},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["result"]["response"]

async def cf_ai_embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using BGE-Base-EN (768-dim)."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{CF_AI_URL}/@cf/baai/bge-base-en-v1.5",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            json={"text": texts},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["result"]["data"]
```

---

## 8. Git Workflow

### Branch Naming
```
feat/uc1-eval-engine-code-grader
feat/uc2-http-proxy-intercept
feat/uc3-rovo-agent-fetch-incident
fix/replay-bisect-hash-mismatch
```

### Commit Format — Conventional Commits
```
feat(eval-engine): add position-bias calibration to LLM judge
fix(atlassian-agent): handle JSM 429 rate limit with exponential backoff
test(flight-recorder): add deterministic replay test with cassette fixture
chore(infra): update wrangler.toml with D1 database ID
```

**Commit frequently** — every logical checkpoint (passing test, completed function).
**Run before every commit:** `make check && make test`

---

## 9. Architecture Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| Setup | Use Cloudflare Workers AI instead of Anthropic API | No Anthropic API key available; CF Workers AI free tier sufficient |
| Setup | Use MinIO instead of Cloudflare R2 | R2 requires credit card; MinIO already running in Langfuse Docker stack |
| Setup | Skip Cloudflare Queues | Authentication issues + not critical for hackathon; use sync eval calls |
| Setup | Atlassian JSM project key is AO (not SENT) | AO is the JSM project with Incident issue type (ID: 10013) |
| Setup | Use issue type ID 10013 (not name) | `[System] Incident` name rejected by API; ID works |
| Init | OTel GenAI `gen_ai.*` spans as shared trace format | Industry standard, positions replay extension as real protocol contribution |
| Init | httpx transport override for LLM interception | No proxy process; works inside SDK transparently |
| Init | Pydantic structured outputs for all tool calls | Required for deterministic replay (AgentRR insight) |
| Init | xqdrant replaces Cloudflare Vectorize for similarity search | xqdrant adds dimension attribution + confidence margin (explainability layer) |

---

## 10. Known Issues / Gotchas

| Issue | Context | Solution |
|---|---|---|
| JSM issue type must use ID | `[System] Incident` name returns 400 | Use `{"id": "10013"}` in issue creation |
| JSM no priority/labels fields | AO project rejects priority + labels | Omit both fields when creating Jira issues in AO |
| Confluence duplicate page titles | Re-running seed fails | Script handles this — skip runbooks if already seeded |
| Langfuse URL was 4-level domain | `langfuse.ains.ahmedxsaad.me` → SSL cipher error | Moved to `langfuse.ahmedxsaad.me` (3-level, covered by CF cert) |
| git remote uses wrong token | Fine-grained token had no write access | Use classic token (ghp_...) with `repo` scope |
| xqdrant port 6333 is internal | Never expose via Cloudflare Tunnel | Only `atlassian-remote` calls it directly on localhost |
| MinIO port 9090 is internal | Never expose via Tunnel | Use S3 client with `endpoint_url=http://localhost:9090` |
| CF env var deprecation | `CF_API_TOKEN` → `CLOUDFLARE_API_TOKEN` | Use `CLOUDFLARE_API_TOKEN` in all new code |
| JSM pagination differs | JSM uses `start`/`limit`, Jira uses `startAt`/`maxResults` | Never mix them |
| Atlassian rate limits (March 2026) | 65K points/hr global pool | Always use `api_call_with_backoff()` |
| OTel GenAI conventions experimental | Opt-in required | Set `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` |
| CF Workers AI returns parsed JSON | Llama 3.3 70B sets `result.response` to a **dict** (not str) in JSON mode, breaking `model_validate_json`/`_extract_json` | `cf_ai_chat` re-serializes dict/list responses to a JSON string (`_response_text`) in both clients |
| xqdrant collections must be seeded | `incidents`/`runbooks` are created empty — `/analyze` returns no evidence until vectors are loaded | Run `make seed-xqdrant` (embeds AO incidents + SENT runbooks). Seeded live: 101 incidents + 11 runbooks |
| `/srv/sentinel/.env` drifted from the code | Was missing `FORGE_REMOTE_SECRET`/`AUDIT_HMAC_KEY`/`CF_D1_DATABASE_ID` and had `ATLASSIAN_JIRA_PROJECT_KEY=AINS` (→ Jira 400) | Reconciled 2026-06-20 to `AO` + the missing vars; D1 id is `7bf67c82-…` |
| Langfuse SDK is **v4**, not v2 | `pyproject` pins `langfuse>=4.9.1`; the v2 `langfuse.generation()`/`.span()` factories were removed and `.end(output=…)` no longer takes output | Use `Langfuse.start_observation(name=…, as_type="generation"\|"span", model=…, input=…)`, then `obs.update(output=…)` + `obs.end()`. Wrapped in `<pkg>/langfuse_client.py` (`start_generation`/`start_span`/`end_observation`) |
| Langfuse SDK can't deliver to the **public** host | `LANGFUSE_HOST=https://langfuse.ahmedxsaad.me` 403s the SDK (CF bot challenge) → `Failed to export span batch code: 403` | Deliver to `LANGFUSE_HOST_INTERNAL=http://127.0.0.1:3000` (the `langfuse-web` container; **use `127.0.0.1`, not `localhost`** — `localhost`/IPv6 times out). `get_langfuse()` prefers it, falls back to `LANGFUSE_HOST`. Keep the public host for human links only |
| Tracing must never fail the request | A Langfuse outage/misconfig should not break `/evaluate` or `/analyze` | `get_langfuse()` returns `None` when `LANGFUSE_*` is unset and every helper no-ops; the SDK exports in a background thread, so a delivery 403 is logged but non-fatal. Tests mock `get_langfuse` → `None` (autouse fixture) |
| CF Workers AI free tier rate-limits embeddings under heavy load | 429s (and transient 5xx) during bursty embed/RCA/judge calls | Retry with 30s backoff is now built in (`cf_ai_client._post`, both packages: 429 → 30s ×3, 5xx → 5s ×2, via `asyncio.sleep`; warns on each retry), but space test calls >3s apart. Tests mock the backoff (`monkeypatch.setattr("asyncio.sleep", ...)`) so they never actually wait |
| Jira "Duplicate" link type may be absent | `POST /rest/api/3/issueLink` with a type name fails if that link type isn't configured on the site (analogous to "use issue-type ID not name") | Link type is configurable via `ATLASSIAN_DUPLICATE_LINK_TYPE` (default `Duplicate`); verify with `GET /rest/api/3/issueLinkType` before the demo, create it or repoint to e.g. `Relates` |
| CF daily neuron allocation 429 (`code 4006`) | CF returns `429` `code 4006` ("daily free allocation of 10,000 neurons") for **every** active model — **even when the dashboard shows `0/10k`**. Verified the token is valid + sees only the correct account, and a deprecated model gives a *different* 410 (so requests reach the AI layer — not auth). Token lacks analytics-read scope, so CF's authoritative usage can't be queried to reconcile. Leading theory: **rolling ~24h enforcement** vs a **calendar-day display** panel (yesterday's E2E ran ~14:00 UTC → clears ~14:00 UTC next day). The plain 30s×3 retry burned 90s then surfaced as a bare **500**, hanging past Forge's 25s. | `cf_ai_client._post` **fails fast** on a 4006/"neurons" 429 (no backoff) in **both** packages; `api.py` (eval-engine + atlassian-remote) maps any upstream `httpx.HTTPStatusError` to a clean **503**. Verified live: `/search`→503 in 0.11s, `/analyze`→503 in 5s. Re-test after ~14:00 UTC or demo from cassettes via deterministic `/replay` (0 live calls) |
| Runbooks always returned 0 hits | `VECTOR_SIMILARITY_THRESHOLD` (0.75) was imported from `trace_core`, so the `.env` knob was **ignored**; incident→runbook cosine tops ~0.71 (generic templated runbooks) < 0.75 → every runbook filtered out (incident→incident is 0.76–0.79, so incidents passed) | Per-collection floors in `atlassian_remote.config`: incidents use `VECTOR_SIMILARITY_THRESHOLD` (env-overridable, 0.75); runbooks use `RUNBOOK_SIMILARITY_THRESHOLD` (env-overridable, **0.60**). `search_similar(..., threshold=None)` resolves by collection. Re-seed richer runbook content to lift scores |
| UC1 | Drift detection combines verdict/score deltas **and** semantic output-embedding drift (not just pass-rate) | Brief Scenario B: a model update can shift output *characteristics* with no pass/fail change; the BGE embedding-centroid distance catches what verdict drift alone misses |
| UC1 | Evaluator-quality headline metric is **Cohen's κ**, not raw accuracy | Brief §2.4 "evaluation of the evaluator": raw accuracy flatters a constant-verdict judge on an imbalanced gold set; κ chance-corrects so a judge that always says "pass" scores ~0 |
| CF model response shapes differ across models | `result.response` (older, e.g. llama-3.3-70b) vs OpenAI-style `result.choices[].message.content` (newer) vs `message.reasoning` with `content: null` (reasoning models, e.g. **gemma-4-26b-a4b** — a poor fit for fast structured JSON; **gemma-3-12b is 410 Gone**) | `cf_ai_client._response_text` (both packages) reads `response`, then falls back to `choices[0].message.content`, then `.reasoning`. Main model is **`@cf/meta/llama-3.1-8b-instruct-fp8-fast`** — clean JSON `content`, ~6x cheaper out than 70B, fast for Forge's 25s |
| Workers AI on a separate CF account | `CF_AI_ACCOUNT_ID`/`CF_AI_API_TOKEN` route **only** the AI calls to another account (e.g. a teammate's) for a fresh 10k-neuron/day budget; D1 stays on `CLOUDFLARE_*` | `cf_account_id()`/`cf_api_token()` prefer `CF_AI_*`, fall back to `CLOUDFLARE_*`. Verified live: `/analyze` generated on the teammate account while the primary was at 0, and D1 writes still landed on the primary |

---

## 11. Current Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Foundation | ✅ Done | Azure VM, Langfuse, xqdrant, D1, Vectorize, MinIO, Atlassian, 100 incidents seeded |
| Foundation — `trace-core` | ✅ Done | Shared contract complete: constants, Pydantic v2 schemas, hash_utils, OTel GenAI span helpers, schema.ts mirror. `make test-core` green (21 tests); ruff/black/isort/mypy --strict clean on the package |
| Phase 1 — UC2 Flight Recorder | ✅ Done | cassette (now carries full `records` for non-lossy traces), RecordingTransport **+ AsyncRecordingTransport**, @record_tool, hash-chain audit, D1/MinIO clients, replay + bisect, `manifest.write_run_manifest`, FastAPI on 8001. Exercised live by the Phase 4 loop. `make test-uc2` green (30 tests); ruff/black/isort/mypy --strict clean |
| Phase 2 — UC1 Eval Engine | ✅ Done | cf_ai_client, safety pre-filter (Llama Guard), code grader, calibrated LLM judge (mandatory position-bias calibration), DAG failure attribution, pass^k (all() not any()), **drift detection** (`drift/` → `DriftReport`; `POST /drift`), **evaluator-quality** (judge-vs-human Cohen's κ → `EvaluatorQuality`; `POST /evaluator-quality`), verdict reporter (files AO Jira issue, type id 10013, no priority/labels; filing now **best-effort**), FastAPI on 8000. `trace_loader` loads the **full MinIO cassette** (`cassette_store`; D1 previews are fallback). Verdicts now **persist to D1 `eval_verdicts`** best-effort (`verdict_store.persist_verdict`, mirrors the flight-recorder D1 write side). `cf_ai_client._post` retries CF Workers AI 429/5xx with backoff. `make test-uc1` green (59 tests); ruff/black/isort/mypy --strict clean |
| Phase 3 — UC3 Atlassian Agent | ✅ Done | Cores built: `atlassian-remote` (FastAPI :8080 — `/analyze` `/duplicates` `/search` `/embed` `/health`; embeddings, xqdrant search, RCA drafting, semantic duplicate resolver; `/analyze` records + evals — see Phase 4) and `atlassian-agent` (Forge Rovo agent + 7 actions, incl. `resolve-duplicate` → auto-links Jira duplicates). `make test-uc3` green (43 Python + 25 TS tests); clean. **Forge cloud deploy DONE:** `forge deploy -e development` (v2.2.0) + **installed on Jira AND Confluence** at ahmedains.atlassian.net (status Up-to-date); `FORGE_REMOTE_URL`/`FORGE_REMOTE_SECRET` (encrypted) variables set. The Forge CLI runs on the VM (logged in via `FORGE_EMAIL`/`FORGE_API_TOKEN` = the Atlassian creds, `FORGE_DISABLE_ANALYTICS=true` for non-TTY) |
| Phase 4 — Integration | ✅ Done (live-validated) | **End-to-end loop wired:** `POST /analyze` generates a `run_id`, records every RCA-gen CF Workers AI call into a MinIO cassette via `AsyncRecordingTransport` (hash-chain audit → D1), writes a `run_manifests` row, then `POST`s the `run_id` to eval-engine `:8000/evaluate` (which loads the cassette, judges, and files the Jira Incident on fail/flag). Response envelope gains `run_id` + `eval_verdict` + `replay_link`. Internal calls use localhost (eval `:8000`, MinIO `:9090`), never tunnel URLs. `tests/integration/test_full_loop.py` proves it end-to-end with all boundaries mocked. **Live-validated on the VM** (2026-06-20): `POST /analyze AO-1` → 200 with full `eval_verdict`, cassette in MinIO, `run_manifests` row, eval-engine filed an AO Incident; xqdrant seeded (101 incidents + 11 runbooks) so retrieval returns evidence. Remaining: Forge deploy |
| Phase 5 — Differentiators | 🟦 In progress | **Dashboard done** (`packages/dashboard`): Next.js 16 App Router (Turbopack) + Tailwind + hand-rolled shadcn-style primitives + Framer Motion. All 5 screens (`/` overview · `/runs` · `/runs/[run_id]` trace · `/verdicts/[run_id]` · `/replay/[run_id]`) + `api/{replay,bisect}` server proxies. `?mock=true` on every page with automatic live→mock fallback (`lib/api.ts` + `lib/mock-data.ts`; `DataSourceBadge` shows live/mock/fallback). `pnpm --filter dashboard build` + `typecheck` + `lint` all green; smoke-tested all 6 routes → 200 in mock mode. **Langfuse tracing done + live-verified** (2026-06-21): the 3 Python services trace every LLM call (`llm-judge`, `rca-generation`) + vector search (`xqdrant-search`) via the Langfuse v4 SDK (`<pkg>/langfuse_client.py`, init at `api.py` startup), delivering to `LANGFUSE_HOST_INTERNAL` (127.0.0.1:3000) — confirmed a live `xqdrant-search` trace landed in Langfuse. Remaining: eval-engine **drift detector** (`drift/detector.py` + `embedder.py` → Cloudflare Vectorize) |

**⚡ Next task: deploy UC3 to Forge + finish Phase 5 differentiators.** The Phase 4 loop is wired and **live-validated** on the VM (`POST /analyze` → record → eval → Jira Incident; xqdrant seeded so retrieval returns evidence). Remaining: (1) `forge register` + `forge deploy --environment development` + `forge install`, setting `FORGE_REMOTE_URL`/`FORGE_REMOTE_SECRET` Forge variables (Forge CLI is not installed on the VM — run from a workstation with an Atlassian login); (2) Phase 5 — the **dashboard is now built** (`packages/dashboard`; build/typecheck/lint green — see the dashboard build note below), so the remaining differentiator is the eval-engine **drift detector** (`drift/detector.py` + `embedder.py` → Cloudflare Vectorize). Note: `pnpm install` now works in this environment (the `minimumReleaseAge` lockfile policy is gone; the dashboard installed and built cleanly). Reuse `normalize_request` / `hash_step_key` from `trace_core` for cassette keys — do not redefine them.

> **eval-engine build notes (18 Jun 2026):**
> - **Layout:** repo convention `packages/eval-engine/src/eval_engine/` (imported as `from eval_engine.graders.code_grader import ...`); `api.py` at the package root (run `uvicorn api:app --port 8000`). The task's `src/cf_ai_client.py` etc. map under `src/eval_engine/`.
> - **Pipeline (`verdicts/reporter.evaluate_run`):** safety pre-filter (short-circuits to `fail` if unsafe, skips the judge) → deterministic `code_grader` → `calibrated_judge` → `dag_attributor` → `EvalVerdict` with `SelfEvaluation`. Files an AO Jira Incident on `fail`/flag (issue-type id `10013`, **no** priority/labels), no-op when Atlassian env is unset.
> - **Position-bias calibration is always on:** `calibrated_judge` runs the judge twice with rubric dimensions reversed; a verdict flip → `uncertain` + `flag_for_human` (`reason="position_bias_detected"`). Verdict per pass is derived from the mean dimension score vs `JUDGE_PASS_THRESHOLD` (0.6).
> - **`pass^k` uses `all()`:** `metrics.pass_at_k.pass_at_k(results, k=PASS_AT_K_TRIALS)` — empty or any-fail → 0.0.
> - **Async + mockable:** all CF Workers AI calls go through `cf_ai_client` (`cf_ai_chat`/`cf_ai_embed`/`cf_ai_safety`); tests monkeypatch those module functions (no network). Added `pytest-asyncio` (`asyncio_mode = "auto"`) to the dev group and `packages/eval-engine` to the workspace.
> - **Tooling:** `make typecheck` now runs **per-package** mypy — a single recursive `mypy packages/` collides on the duplicate root-level `api.py`/`conftest.py` module names across packages (atlassian-remote will add a third `api.py`).

> **flight-recorder build notes (18 Jun 2026):**
> - **Layout:** follows the repo convention `packages/flight-recorder/src/flight_recorder/` (importable as `from flight_recorder.proxy.cassette import ...`), so on-disk path == import path and `mypy --strict` stays clean. The task's `src/proxy/...` paths map to `src/flight_recorder/proxy/...`. `api.py` is at the package root (run `uvicorn api:app --port 8001`).
> - **`FLIGHT_MODE`** is resolved once in `flight_recorder.config.resolve_mode()` and threaded through `RecordingTransport` and `@record_tool`; default is `record`.
> - **Env vars:** new code uses `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` (per §10 gotcha), plus `CF_D1_DATABASE_ID`, `AUDIT_HMAC_KEY`, and the `BLOB_STORAGE_*` set. `.env.example` was reconciled (2026-06-19) to list exactly what the code reads (added `CF_AI_MODEL_*`, `BLOB_STORAGE_*`, `XQDRANT_*`, `FLIGHT_RECORDER_URL`; dropped `ANTHROPIC_API_KEY`, `CF_R2_BUCKET`).
> - **Storage is mockable:** `storage.minio_client.{store,load}_blob` and `storage.d1_client.insert/query` are module-level functions tests monkeypatch, so the whole record/replay loop runs with zero network. All HTTP in tests is mocked via `pytest-httpx`.
> - **Workspace:** added `packages/flight-recorder` to `[tool.uv.workspace] members`; added `pytest-httpx` + `pytest-cov` to the dev group; added a mypy override ignoring missing stubs for `boto3`/`botocore`/`uvicorn`/`mypy_boto3_s3`.

> **Phase 4 integration build notes (20 Jun 2026):**
> - **The loop:** `atlassian_remote.analyzer.analyze_incident` → `run_id = recording.new_run_id()` → `with recording.RunRecorder(run_id)` (binds an `AsyncRecordingTransport` as `cf_ai_client`'s active transport via a **contextvar**, so every embed/RCA CF Workers AI call is taped) → `recording.persist_manifest` (writes a `run_manifests` D1 row, best-effort) → `eval_client.request_evaluation(run_id)` (`POST {EVAL_ENGINE_URL}/evaluate`). Response = `AnalyzeResult{run_id, rca_draft, similar, runbooks, flag_for_human, eval_verdict, replay_link}`.
> - **Cassette is now the non-lossy source of truth:** `cassette.save_to_cassette(..., record=...)` appends each step's full `TraceRecord` (JSON-mode) to a new `records` list alongside `steps` (replay/bisect untouched — they still read `steps`). `eval_engine.trace_loader.load_trace` prefers `eval_engine.cassette_store.load_cassette_records` (boto3 MinIO read) and only falls back to the D1-preview HTTP path when no cassette exists. `write_audit_record` return type is unchanged (`str` payload_hash); the cassette record's audit block is built from `prev_hash` + that hash + `sign()`.
> - **Sync vs async transport:** `RecordingTransport` is sync (`httpx.BaseTransport`); the new `AsyncRecordingTransport` (`httpx.AsyncBaseTransport`) shares all record/replay logic via a `_RecordingCore` mixin. `close()`/`aclose()` close **and null** the inner transport so one recorder survives the multiple short-lived `httpx.AsyncClient`s the analyze flow opens (embed + embed + RCA) — the audit chain links across them.
> - **Internal vs tunnel URLs:** eval-engine is called at `EVAL_ENGINE_URL` (default `http://localhost:8000`); MinIO/xqdrant stay on localhost. `replay_link` uses `FLIGHT_RECORDER_URL` (default the **public** `https://flight.ahmedxsaad.me`) because it's a human-clickable deep link. New env var: `EVAL_ENGINE_URL` (added to `.env.example`).
> - **New cross-package deps:** `atlassian-remote` now depends on `flight-recorder` (workspace); `eval-engine` gains `boto3` (cassette read). `recording.persist_manifest` + `eval_client.request_evaluation` are **best-effort** (log + continue / return `None`) so an eval/recorder outage never fails the incident analysis. Tests mock all boundaries; `make test-uc2/uc1/uc3` Python all green (30/22/31), mypy --strict + ruff/black/isort + check-docs clean.
>
> **trace-core build notes (18 Jun 2026):**
> - **Layout:** standard src-layout — the importable package is `packages/trace-core/src/trace_core/`, imported as `from trace_core import ...`. No `sentinel.` namespace prefix (it added repetition with the repo name and a nesting level for no benefit). Future Python packages follow the same shape: `packages/<pkg>/src/<pkg>/`, imported as `from <pkg> import ...`.
> - **Workspace:** a root `pyproject.toml` now defines the uv workspace (`make setup` → `uv sync --all-packages`) and the shared tooling config (pytest, mypy --strict + pydantic plugin, ruff, black, isort). Add future Python packages to `[tool.uv.workspace] members`.
> - **`make check` is not yet green repo-wide** — blocked only by items outside trace-core: pre-existing lint errors in `scripts/seed_atlassian.py` + `scripts/run_synthetic_eval.py`. (The `dashboard` TS package now has a `package.json` and its build/typecheck/lint are green — see the dashboard build note.) trace-core itself passes ruff/black/isort/mypy/pytest.

> **atlassian-remote build notes (19 Jun 2026):**
> - **Layout:** repo convention `packages/atlassian-remote/src/atlassian_remote/` (imported as `from atlassian_remote.vector_search import ...`); `api.py` at the package root (run `uvicorn api:app --port 8080`). The task's `src/cf_ai_client.py` etc. map under `src/atlassian_remote/`. `minio_client.py` was **not** built — none of the four endpoints need blob storage, so boto3 is not a dependency here.
> - **`/analyze` pipeline (`analyzer.analyze_incident`):** `AtlassianClient.get_issue` → flatten summary + ADF description to text → `vector_search.search_similar` over the incidents **and** runbooks collections → `rca_generator.generate_rca` → `RcaDraft`. `flag_for_human` (`confidence_score < CONFIDENCE_THRESHOLD`, 0.70) is computed in `rca_generator.needs_human_review` and returned on the `AnalyzeResult` envelope — **`RcaDraft`'s shared schema is left untouched** (it has no such field).
> - **xqdrant:** qdrant-client 1.18 removed `.search` → uses `query_points`. Filters `score > VECTOR_SIMILARITY_THRESHOLD` (0.75) and **always** populates `SearchResult.attribution` (uses the payload block if present, else synthesises one with `confidence_margin` = score gap to the next hit). Client + embed call are module-level so tests monkeypatch them (no network/server).
> - **Atlassian client:** HTTP Basic; **exponential backoff on 429** (honours `Retry-After`, caps at 8s, sleep isolated in `_backoff_sleep` so tests run instantly). `build_incident_fields` enforces issue-type id `10013` and omits priority/labels.
> - **API:** FastAPI on 8080. `verify_request` (`Depends`) checks `X-Sentinel-Secret` with `hmac.compare_digest` on `/analyze` `/search` `/embed`; `/health` is open (tunnel liveness). All CF Workers AI goes through `cf_ai_client` (`cf_ai_chat`/`cf_ai_embed`), monkeypatched in tests.
> - **Tooling:** added `packages/atlassian-remote` to the uv workspace + the `make typecheck` loop; `qdrant_client.*` added to the mypy missing-imports override. `uv run pytest packages/atlassian-remote/tests/` green (30 tests); ruff/black/isort/mypy --strict + `make check-docs` clean.

> **atlassian-agent build notes (19 Jun 2026):**
> - **Shape:** Forge app — `manifest.yml` (renamed from `forge.yml`) declares one `rovo:agent` plus 7 `action` + 7 `function` modules; handlers are re-exported from `src/index.ts` (`handler: index.<fn>`). `app.id` is now a **real registered ARI** (`forge register` done) — remaining is `forge deploy` + `forge install`.
> - **7 actions:** `fetch-incident` (native Jira read) · `search-similar-incidents` / `search-runbooks` (→ remote `/search`) · `post-rca-comment` (→ remote `/analyze` → ADF Jira comment) · `resolve-duplicate` (→ remote `/duplicates` → auto-links Jira issues + ADF comment when confident) · `draft-pir-page` (→ `/analyze` → Confluence page via ADF/`atlas_doc_format`) · `flag-knowledge-gap` (native AO issue, id 10013). Not every action hits the remote — `fetch` and `flag` are Atlassian-native by design.
> - **lib:** `remote.ts` adds `X-Sentinel-Secret` + `X-Account-Id` and backs off on 429; `atlassian.ts` wraps `@forge/api` (`asApp().requestJira/requestConfluence`); `adf.ts` builds **all** Jira/Confluence bodies as ADF and flattens ADF descriptions back to text.
> - **Tooling:** added a root `pnpm-workspace.yaml` so `pnpm --filter atlassian-agent <script>` resolves. `pnpm --filter atlassian-agent test` green (25 jest tests; `@forge/api` is a manual mock under `tests/__mocks__`); `tsc --noEmit` (strict) + eslint + prettier all clean.
> - **Forge cloud deploy DONE (2026-06-23):** the Forge CLI (12.22.0) is installed on the VM; logged in non-interactively via `FORGE_EMAIL`=`ATLASSIAN_EMAIL` + `FORGE_API_TOKEN`=`ATLASSIAN_API_TOKEN` + `FORGE_DISABLE_ANALYTICS=true` (the analytics consent prompt blocks non-TTY otherwise). `forge deploy -e development` (v2.2.0) + `forge variables set` (`FORGE_REMOTE_URL`, encrypted `FORGE_REMOTE_SECRET`) + re-deploy + `forge install`/`--upgrade`. The app is **installed on Jira AND Confluence** at ahmedains.atlassian.net (status Up-to-date). `forge install list` confirms both. (`forge deploy` reports a non-blocking lint warning — 1 issue.)

> **dashboard build notes (20 Jun 2026):**
> - **Stack:** Next.js 16 App Router (Turbopack builds; React 18.3 — Next 16's peer deps allow `^18.2`) + Tailwind + **hand-rolled shadcn-style** primitives (`components/ui/*`) — built by hand instead of via the shadcn CLI so the build needs no network. Framer Motion for every animation; lucide-react icons. Fonts use **system stacks** (`app/globals.css`), not `next/font/google`, so the production build never depends on a remote font host. `params`/`searchParams` are awaited Promises (Next 15+). Port **3001**.
> - **Server-fetch + mock pattern:** pages are server components that call `lib/api.ts`; each accessor returns `Loaded<T> = {data, source, error?}` (`live | mock | mock-fallback`). `?mock=true` (read via `isMock(searchParams)`) returns `lib/mock-data.ts` fixtures; otherwise it server-fetches the live URL and **falls back to mock on ANY failure** (so no screen ever breaks during judging). Animation/interactivity live in `components/sentinel/views/*View` client components; `app/api/{replay,bisect}/route.ts` are server-side POST proxies (no browser CORS, no client secrets). `SiteHeader` threads `?mock=true` through nav + a toggle.
> - **API reality:** the **eval engine has no `GET /verdicts[/{id}]`** (only `/health` + `POST /evaluate`), so the home "Recent verdicts" table + verdict detail run on **mock-fallback** in live mode — the UI optimistically tries those GETs and will light up if added. `GET /runs/{id}` trace rows carry `input_preview`/`output_preview` but **no latency** (`metadata_json` is just the hmac algo), so `StepTimeline` shows `latency_ms` only when present. `lib/types.ts` mirrors `trace-core/schema.ts` (separate Next workspace → can't import it).
> - **Lint:** Next 16 removed `next lint`; `"lint": "eslint ."` runs ESLint 9 against a **flat config** (`eslint.config.mjs`) that spreads `eslint-config-next`'s **native flat array** (NOT FlatCompat + `next/core-web-vitals`, which throws "Converting circular structure to JSON" with the v16 plugins).
> - **Build gate gotcha:** a supply-chain policy hook adds `allowBuilds:` to the root `pnpm-workspace.yaml`; `unrs-resolver` (optional native eslint-resolver binary) and `sharp` (Next 16's `next/image` optimizer — unused here) are both set to **`false`** — without an explicit decision, `pnpm <script>`'s pre-run check fails with `ERR_PNPM_IGNORED_BUILDS`.
> - **Deployed (2026-06-20):** runs on the VM as the **`sentinel-dashboard`** systemd unit (`node …/next/dist/bin/next start -p 3001`, enabled, auto-restart) and is exposed at **`https://dashboard.ahmedxsaad.me`** via a new `sentinel`-tunnel ingress rule (→ `localhost:3001`) + a proxied DNS CNAME. The unit sets `FLIGHT_RECORDER_INTERNAL_URL=http://localhost:8001` and `EVAL_ENGINE_INTERNAL_URL=http://localhost:8000` so **server-side fetches hit the services directly** — `/runs` + `/runs/[id]` now show **LIVE** data (verdict screens still mock-fallback: eval has no `GET /verdicts`). Clickable links (replay deep-link, Langfuse) stay on the public URLs. `lib/api.ts` split: public `*_URL` consts for links vs internal `*_API` (`FLIGHT_RECORDER_INTERNAL_URL`/`EVAL_ENGINE_INTERNAL_URL`, default to the public URL) for fetches.
> - **Status:** `pnpm --filter dashboard build` + `typecheck` + `lint` all green; all 6 routes smoke-tested → 200 in mock mode; `/runs` confirmed LIVE on the VM. Added `packages/dashboard` to `pnpm-workspace.yaml`. Not done: no unit-test framework wired (the `test` script runs `tsc --noEmit`).

---

## 12. Evaluation Checklist (Run Before Demo)

- [ ] `make test` passes with zero failures
- [ ] `make check` passes with zero lint/typecheck errors
- [ ] No `.env` values committed to git
- [ ] No `TODO`/`FIXME` comments in `main` branch
- [ ] Every Python function has a docstring
- [ ] Every exported TypeScript function has JSDoc
- [ ] `make check-docs` passes (`.env.example` parity with code + no doc drift markers)
- [ ] `make eval` produces a report with `pass^k` metric
- [ ] End-to-end demo scenario runs without manual intervention

---

## 13. Outstanding TODOs — Security (from the UC1/UC2 code review, 2026-06-19)

> None block local dev, but all should be closed before the public demo: the FastAPI services are
> exposed to the internet via Cloudflare Tunnel. Severity in parentheses.

- [ ] **(Medium) Authenticate the public APIs.** `eval-engine` (`:8000`) and `flight-recorder`
      (`:8001`) currently have **no auth**. `GET /runs` + `/runs/{run_id}` expose recorded traces
      (prompt / incident contents); `/replay`, `/bisect`, `/evaluate` are freely triggerable. Add
      the same shared-secret check `atlassian-remote` uses (`X-Sentinel-Secret` via a FastAPI
      `Depends`).
- [ ] **(Medium) `/evaluate` abuse vector.** It accepts arbitrary `records` (runs the LLM judge →
      burns CF Workers AI neurons, no rate limit) and `file_issue` defaults to `True`, so an
      unauthenticated failing/flagged trace **creates a Jira Incident in AO**. Require auth, default
      `file_issue=False` on the public route, and cap `/evaluate/batch` size.
- [ ] **(Low) Harden `d1_client.insert` identifiers.** Table/column names are interpolated into the
      SQL string (values are parameterized with `?`). Safe today — callers pass constants — but add
      an identifier allowlist / `^[A-Za-z_][A-Za-z0-9_]*$` check to remove the latent injection sink.
- [ ] **(Low) Validate `run_id` as a UUID** before using it as a MinIO object key (`{run_id}.json`)
      and in `trace_loader` URL paths.
- [ ] **(Info) Wire structured logging.** `LOG_LEVEL` exists in `trace_core` but no logger is set up;
      add request/audit logging to the services.
- [ ] **(Info) Run a real eval report.** `docs/eval_report.md` is still a hand-authored
      template with placeholder metrics (`—`/`%`) — it has **never** been produced by a live
      `make eval` run. Its evaluator-model references were corrected (2026-06-20) to the CF
      Workers AI Llama model, but `scripts/run_synthetic_eval.py` writes a different structure
      (and emits no model line), so a real `make eval` (800 trials) is still needed to populate
      it; reconcile the per-dimension table with `JUDGE_DIMENSIONS` (correctness/efficiency/
      safety/reasoning_quality) when it is.

---

*Last updated: 2026-06-24 by Claude Code (Sonnet 4.6) — **Dashboard UI polish: research-rigour section + reliability discovery.** HomeLanding.tsx: added "Rigour behind every verdict" section with 4 metric cards (pass^k 100%→33% / τ-bench arXiv 2406.12045, 2× rubric calibration / AgentRewardBench arXiv 2504.08942, per-step VeriLA attribution, Cohen's κ=0.60 / Landis & Koch) so judges see the research backing on the landing page without navigating; added third hero CTA "Reliability metrics" → /reliability; added /reliability to footer links; updated LOOP[02] body to mention Forge deploy explicitly. ReliabilityView.tsx: added two-card context strip explaining drift detection and Cohen's κ (with AgentRewardBench citation) immediately above the panels. SiteHeader.tsx: active nav item now gets bg-white/8 pill background instead of text-color-only change. All gates clean: `tsc --noEmit` exit 0, `eslint .` exit 0, `next build` exit 0. PREVIOUS: 2026-06-24 by Claude Code (Opus 4.8) — **Observability + chaos engineering on the K8s/KEDA branch** (`feat/k8s-keda-scalability`, all under `deploy/`, no run-path changes). Builds on the branch's Minikube + KEDA work (one Python image for all 3 FastAPI services, namespace `sentinel`, gitignored config/secret from `.env`, CPU-trigger ScaledObject — KEDA verified live scaling eval-engine 1→3 at `cpu 43%/50%`). **(1) Observability (`deploy/observability/`):** the 3 FastAPI services now expose **`GET /metrics`** via `prometheus-fastapi-instrumentator` (added to each `pyproject.toml` + a 1-line `Instrumentator().instrument(app).expose(app)` in each `api.py`, after `init_langfuse()`; mypy override for the un-stubbed module; `uv.lock` regenerated → image picks it up via `--frozen`). Added a Minikube-tuned **kube-prometheus-stack** values file (disables etcd/scheduler/controller/proxy scrape jobs, `serviceMonitorSelectorNilUsesHelmValues:false`, Grafana pass `sentinel`, sidecar `searchNamespace:ALL`), **3 ServiceMonitors** (scrape `port: http` `/metrics`), and an auto-imported **Grafana dashboard** (7 panels: KEDA replicas, running pods, per-pod CPU/mem, request rate, p95 latency, restart recovery). **(2) Chaos (`deploy/chaos/`):** scripted `pod-kill.sh` + `steady-state.sh` (kubectl-only self-healing/availability proof) **and** Chaos Mesh manifests (`pod-kill` Schedule, `network-delay`, `cpu-stress` → drives KEDA scale-out under chaos). **(3) Helm:** new gated `templates/servicemonitor.yaml` + `monitoring.{enabled,releaseLabel,interval}` values (off by default; renders 3 ServiceMonitors when on). **Non-regression verified:** `prometheus-fastapi-instrumentator` v8.0.2 resolved; **167 Python tests pass**, per-package mypy --strict + ruff clean on all 3 modified packages; `/metrics` smoke-tested (200, `http_requests_total`/`http_request_duration_seconds`); `helm lint` clean + template renders (0 ServiceMonitors off, 3 on); dashboard JSON + chaos scripts syntax-validated. No new env vars → `.env.example` parity unaffected. PREVIOUS: 2026-06-23 by Claude Code (Opus 4.8) — **Forge cloud deploy DONE + mid-replay injection surfaced in the UI.** (1) **UC2 divergence editing is now in the dashboard:** flight-recorder `/replay` accepts `inject {step_index: stored_response}` and re-drives the recording from tape via `build_tape_agent` (genuine re-execute, 0 live calls); `ReplayResult.injected_steps`. The replay page gained a "Divergence editing (inject during replay)" panel (step selector + override JSON + Inject & replay) — verified live (`injected_steps=[0]`, 0 live). (2) **Forge cloud deploy COMPLETE:** the Forge CLI is on the VM; logged in non-interactively (`FORGE_EMAIL`/`FORGE_API_TOKEN`=Atlassian creds + `FORGE_DISABLE_ANALYTICS=true`); `forge deploy -e development` (v2.2.0) + `forge variables set` (`FORGE_REMOTE_URL` + encrypted `FORGE_REMOTE_SECRET`) + re-deploy + `forge install --upgrade` → the **Sentinel Incident Responder Rovo agent is installed on Jira AND Confluence** at ahmedains.atlassian.net (status Up-to-date, `forge install list` confirms). Phase 3 → ✅. spec_response: **every UC1/UC2/UC3 Must AND Should is now met and live** (only the optional external-engineer sign-off remains). PREVIOUS: 2026-06-22 by Ahmed Saad (via Claude Code) — **Integrated UC1 Evaluator-Quality** (Ahmed Ben Rejeb's PR #7) onto main alongside saad's verdict-store/trace-UX work: cherry-picked his commit (authorship preserved), resolved the import-union conflict in `eval-engine/api.py` + the §10/§11/Last-updated docs. Evaluator-quality = new `trace_core.EvaluatorQuality` (py+ts) + `eval_engine/metrics/evaluator_quality.py` (Cohen's κ, Landis & Koch bands, per-label recall — chance-corrected judge-vs-human agreement, the brief §2.4 "evaluation of the evaluator" criterion) + `eval_engine/models.GoldCase` + `reporter.evaluate_gold_set` + `POST /evaluator-quality`. Verified green (`make test-core` 21 + `make test-uc1` 59 + check-docs + per-package ruff/mypy --strict), pushed to both remotes, closed PR #7. PREVIOUS: **Richer trace + replay-link + bisect-UX fixes.** Addressed three reported issues: (1) **clicking the replay link showed raw JSON** — `replay_link` pointed at the flight-recorder API `/runs/{id}` (JSON); now points at the **dashboard** `/replay/{id}` human page (new `DASHBOARD_URL` in both configs + `.env.example`; dashboard `replayLink` built from `DASHBOARD_URL`, not the flight API). (2) **"bisect two runs always identical"** — the dashboard form **pre-filled both Good and Bad with the same run id**; now the Bad field starts empty with a placeholder + hint, and the giant embedding-vector output dump is capped. Bisect itself was always correct (two different runs diverge at step 0). (3) **"runs always 3 generic llm_call steps"** — the trace now records the real workflow as **4 steps**: `embedding` (incident embedded once, reused) → `tool_call` xqdrant search **incidents** → `tool_call` xqdrant search **runbooks** → `llm chat` RCA. Added `cassette.append_record` (records-only, no replay step) + `_RecordingCore.record_event` (links the audit chain) + `RunRecorder.record_tool_call`; analyzer embeds once (`search_similar(embedding=…)`) and tapes each retrieval; tool_call records are crafted to **pass the code grader** (tool_name + arguments + non-error output). Dashboard `StepTimeline` gained `vector search` (retrieval) badge. **Verified live:** fresh `/analyze` → 4-step trace, eval still `pass`, replay clean (2 replayable steps, 0 live calls), bisect diverges on different runs, replay link → dashboard. **150 Python tests** (full-loop now asserts the 4-record workflow) + dashboard typecheck/lint/build green; ruff/mypy --strict + check-docs clean. PREVIOUS: **Dashboard reliability pass: live verdict screens, readable trace, replay fixed.** Fixed three dashboard-facing issues: (1) **replay/bisect/verdict "not working"** — the dashboard's server-side fetches used `http://localhost:*`, which Node resolves to IPv6 `::1` first (the IPv4-bound uvicorn services don't answer) → fetches hung to the 5s abort and silently fell back to mock; switched `FLIGHT_RECORDER_INTERNAL_URL`/`EVAL_ENGINE_INTERNAL_URL` to **`127.0.0.1`** (unit + `setup.sh`) + gave replay/bisect a 30s budget → both now `source:"live"`. (2) **trace showed 3 generic `llm_call` steps with raw JSON** — the recorder now tags each step with `operation` (`embedding`/`chat`) + `model_id` and writes human-readable previews ("embed 1 text(s): … → 768-dim vectors" / chat prompt → RCA) into `trace_records` (display-only columns, NOT hashed, so the audit chain is unchanged); `StepTimeline` renders operation badges + model + clean previews. (3) **verdict screens were always mock** — added **`GET /verdicts` + `GET /verdicts/{run_id}`** to eval-engine reading the persisted D1 `eval_verdicts`, so the home table + verdict detail are **LIVE**. Switched Workers AI to a 3rd teammate account (`CF_AI_*`). Verified live on the VM: fresh `/analyze` → trace reads 2 `embedding`(bge) + 1 `llm chat`(llama-3.1-8b); all 5 dashboard screens 200; replay/bisect live (0 live calls). **150 Python tests** (6 verdict-store) + dashboard typecheck/lint/build green; per-package ruff/mypy --strict + check-docs clean. PREVIOUS: **Main model → llama-3.1-8b-fp8-fast + teammate-account Workers AI + FIRST REAL pass^k.** To keep testing without the CF daily wall: (1) tried Gemma but it is unfit — `gemma-3-12b` is **410 Gone** and `gemma-4-26b-a4b` is a reasoning model (`content: null`, answer in `message.reasoning`, no `response` field) — so finalized the RCA+judge model to **`@cf/meta/llama-3.1-8b-instruct-fp8-fast`** (~6x cheaper out than 70B, clean JSON, fast); **hardened `cf_ai_client._response_text`** in both packages to read `response` → `choices[].message.content` → `.reasoning`. (2) Added a **`CF_AI_ACCOUNT_ID`/`CF_AI_API_TOKEN`** split so Workers AI runs on a separate (teammate's) account for a fresh 10k/day while **D1 stays on the primary** (`cf_account_id()`/`cf_api_token()` prefer `CF_AI_*`, fall back to `CLOUDFLARE_*`). **Verified live on the teammate budget:** `/search` 200; full **5-incident E2E** (AO-11/21/51/71/91) all 200 (~20-25s, faster than 70B) with valid RCA + verdict (4 pass / 1 uncertain) + runbooks cited; and a **real `make eval` pass^k** finally completed → **pass@1 100% / pass^8 33.3%** (3 tasks ×8, 4th 503'd as budget ran low; dims: correctness 0.90, safety 0.92, reasoning 0.78, efficiency 0.64) — `docs/eval_report.md` now holds genuine numbers (no longer the template). The 100%→33% gap is the τ-bench headline. **148 Python tests pass** (4 new CF-credential + the model-id assertion updated); per-package ruff/mypy --strict + check-docs clean. New §10 gotchas: CF response-shape variance + the `CF_AI_*` split. PREVIOUS: **Live re-run after CF budget cleared + eval_verdicts persistence fix.** Synced to `origin/main` (pulled the new UC1 **drift detector** `6ee8eb5`), `uv sync` + restarted all 3 services. **CF Workers AI budget cleared on schedule** at ~15:00 UTC (24h after the prior run → confirms the rolling-window theory), so the whole pipeline ran **live**: Issue 1 (`/search`→**200**, 4.3s incidents / 1.4s runbooks), Issue 2 (runbooks now retrieve + are **cited in RCAs** — `/search` top runbook 0.785; per-collection 0.60 floor confirmed live), Issue 3 (Langfuse **53→87** traces, fresh `xqdrant-search`/`rca-generation`/`llm-judge` spans). **5-incident E2E (AO-11/21/51/71/91) all HTTP 200** with real RCA + eval_verdict (3 pass / 1 fail / 1 uncertain) + replay_link; **storage verified** (MinIO 14→21 all 5 found; D1 run_manifests 13→20, trace_records 42→61). **New gap found + fixed:** the D1 `eval_verdicts` table existed but **nothing ever wrote to it** (0 rows) — added `eval_engine/verdict_store.py` (best-effort D1 writer mirroring the flight-recorder `d1_client` write side), wired into `reporter.evaluate_run`, **verified a row landed** (AO-31, `eval_verdicts` 0→1) + 4 regression tests (conftest now unsets `CF_D1_DATABASE_ID` so the persist no-ops in tests). **make eval**: ran clean but the k=8 sweep **re-exhausted the ~10k/day budget mid-run** (the live E2E + sweep consumed it all by ~15:44 UTC → 429 4006 again) → 0 tasks scored (environmental, not logic); real eval evidence is the 6 live single-trial verdicts (4 pass/1 fail/1 uncertain ≈ 67% single-trial). **144 Python tests pass** (130 + 10 drift + 4 new); eval-engine ruff/mypy --strict + check-docs clean. Full writeup rewritten in `docs/test_report.md`. PREVIOUS: 2026-06-22 by Ahmed Saad (via Claude Code) — **Integrated UC1 Drift Detection** (Ahmed Ben Rejeb's PR #6) onto main: cherry-picked his commit (authorship preserved), resolved the import-union conflict in `eval-engine/api.py` + the §10/§11/Last-updated docs (kept saad's comprehensive-test + neuron-quota/runbook-threshold work). Drift = new `trace_core.DriftReport` (py+ts) + `eval_engine/drift/{embedder,detector}.py` + `POST /drift` (pass-rate / per-dimension / semantic-centroid drift vs `DRIFT_*` thresholds, Langfuse-traced, best-effort embed). Verified green (`make test-core` + `make test-uc1` + check-docs + per-package ruff/mypy --strict), pushed to both remotes, closed PR #6. PREVIOUS: **Comprehensive system test + 3 fixes** (full writeup in `docs/test_report.md`). Audited every store (xqdrant 101 incidents/11 runbooks; D1 run_manifests=13/trace_records=42/eval_verdicts=0; MinIO 14 cassettes; AO 103 issues; Langfuse 53 complete traces in project AINS; all 3 services healthy). **Root environmental finding:** the CF Workers AI `run` API returns 429 `code 4006` ("daily free allocation of 10,000 neurons") for every model, **even though the dashboard shows `0/10k`** (unresolved discrepancy — verified valid token + correct single account + deprecated model gives a different 410, so not auth; token can't read analytics to reconcile; leading theory is rolling-24h enforcement vs a calendar-day display panel → likely clears ~14:00 UTC). Either way live embed/LLM/judge calls fail now. **Issue 1 (/search 500):** the embed 429 was retried 90s then surfaced as a 500 — fixed with quota fail-fast in `cf_ai_client._post` + an upstream→**503** handler in `api.py` (atlassian-remote **and** eval-engine); live-verified `/search`→503 in 0.11s, `/analyze`→503 in 5s. **Issue 2 (runbooks 0 hits):** measured incident→runbook cosine on stored vectors (tops ~0.71) vs the 0.75 floor — the `.env` knob was ignored (imported from `trace_core`); fixed with per-collection floors (`RUNBOOK_SIMILARITY_THRESHOLD`=0.60, env-overridable) in `atlassian_remote.config` + `search_similar(threshold=…)`. **Issue 3 (Langfuse):** tracing actually works (53 complete traces, correct project) — "empty" is staleness from the CF outage; also fixed an orphan `xqdrant-search` span on embed failure (try/except ends it). **Issue 4 (E2E):** live blocked by CF; proved the loop via UC2 deterministic `/replay` (live_call_count=0, diverged=false) + recorded artifacts for AO-11/21/51/71/91 (cassette+D1+RCA all present; every RCA cites 0 runbooks = Issue 2 in real output). **Issue 5 (make eval):** fixed two non-CF script bugs (`get_all_runs` read `["runs"]` of a bare list; `dotenv` import made optional) + eval-engine quota fail-fast so the sweep finishes in seconds not hours; report generates (0% — CF blocked), `eval_report.md` left as the committed template. **+7 regression tests; 130 Python tests pass; per-package ruff/mypy --strict + check-docs clean** (`make check` repo-wide still blocked only by PRE-EXISTING `scripts/*.py` lint, unchanged by this work). PREVIOUS: **Synced local `main` to the force-pushed `origin/main`** (rebased linear history + Ahmed Ben Rejeb's UC3 duplicate resolver): `git fetch` showed origin/main force-updated, so `git reset --hard origin/main` (clean tree; my observability/systemd/retry work is present as commits `9201243`/`2a45fb1`/`cb3156e`, nothing lost) + `uv sync --all-packages`. Verified the pulled tree green: **123 Python + 25 jest** tests pass, ruff + per-package mypy --strict (trace-core/flight-recorder/eval-engine/atlassian-remote) + check-docs all clean. Reconciled the one stale current-status count the integration missed — §11 foundation `trace-core` 19→20 (the new `DuplicateVerdict` schema round-trip test); all other §11 counts already correct (uc2 30, uc1 30, uc3 43 Python + 25 TS). PREVIOUS: **Integrated the UC3 Semantic Duplicate Resolver** (Ahmed Ben Rejeb's PR #5) onto the Phase-4/observability `main`: cherry-picked his commit (authorship preserved), resolved the `forge.yml`→`manifest.yml`-rename + additive conflicts (import unions in `analyzer`/`api`/`models`/`test_analyzer`; kept both the Phase-4 `/analyze` envelope and the new `/duplicates`), ran `make test-uc3` + `make check-docs` green, pushed to both remotes. PREVIOUS: **Retry/backoff for CF Workers AI rate limits**: wrapped `_post` in both `cf_ai_client.py` (eval-engine + atlassian-remote) with a retry loop — `429` → `asyncio.sleep(30)` ×3, `5xx` → `asyncio.sleep(5)` ×2, a `logger.warning` on each retry, other statuses/exhausted budgets re-raise `httpx.HTTPStatusError`. Shared config is module-level constants + a `_retry_delay(status, attempt)` helper (identical in both packages). Added 7 retry tests (atlassian-remote `test_cf_ai_client.py` + new eval-engine `test_cf_ai_retry.py`) that mock the wait via `monkeypatch.setattr("asyncio.sleep", ...)` so they assert the backoff schedule with zero real delay; existing tests use 200 responses so the retry path never fires for them. Updated §10 (new gotcha row), §11 current test counts (uc1 26→30, uc3 atlassian-remote 32→35), and the eval-engine/atlassian-remote CLAUDE.md + README cf_ai_client descriptions. Per-package ruff/black/isort/mypy --strict + check-docs clean; eval-engine 30 + atlassian-remote 35 Python tests pass. PREVIOUS: **Promoted the 3 Python services to systemd units**: rewrote `sentinel-eval` (:8000) + `sentinel-remote` (:8080) and **created `sentinel-flight`** (:8001) so all three run `uv run uvicorn api:app --app-dir packages/<pkg>` with `WorkingDirectory=/home/Fantazy/AINS` + `EnvironmentFile=/srv/sentinel/.env` (`Restart=always`, `RestartSec=5`, enabled on boot, logs → `/srv/sentinel/logs/<pkg>.log`). The old units were `inactive` and pointed at empty `/srv/sentinel/{eval-engine,atlassian-remote}` dirs while the live services actually ran as manual `setsid` uvicorn from the working tree; stopped those, `daemon-reload` + `enable --now`, and verified **all three `active (running)`**, health `200`, `/search` `200` under systemd (env incl. `LANGFUSE_HOST_INTERNAL` loaded), and a fresh `xqdrant-search` trace landing in Langfuse. Verified `/srv/sentinel/.env` is systemd-`EnvironmentFile`-safe (no `export`/inline-comments/quotes/spaces). Synced `infra/azure/setup.sh` (corrected both units, added the `sentinel-flight` unit + the enable/start lines) and §0. Committed `feat(observability)` + this infra change and merged both to `main` (non-destructive merge of origin/main PRs #2-#4, no force-push). PREVIOUS: **Langfuse tracing across the 3 Python services**: added a per-package `langfuse_client.py` (eval-engine / atlassian-remote / flight-recorder) — a lazily-cached, env-driven, **best-effort** Langfuse **v4** client (`get_langfuse()` returns `None` when `LANGFUSE_*` is unset → every helper no-ops, so tracing never fails a request). `init_langfuse()` runs at each `api.py` startup. Instrumented `eval_engine/graders/llm_judge.py` (a `llm-judge` generation per judge call → 2 per calibrated judgment), `atlassian_remote/rca_generator.py` (`rca-generation` generation) and `atlassian_remote/vector_search.py` (`xqdrant-search` span, output `{count, top_score}`) via `start_generation`/`start_span` + `end_observation`. **Adapted the task's v2 snippet to the installed v4 SDK** (`langfuse.generation()`/`.span()` and `.end(output=…)` were removed → `start_observation(as_type=…)` + `.update(output=…)` + `.end()`). **Discovered + fixed two infra gotchas:** the v2/v4 API gap, and that the public `LANGFUSE_HOST` 403s the SDK (CF bot challenge → `export span batch code: 403`) — so `get_langfuse()` prefers `LANGFUSE_HOST_INTERNAL=http://127.0.0.1:3000` (use `127.0.0.1`, not `localhost`) and only falls back to the public host; added the var to `.env.example` + `/srv/sentinel/.env` + §3. Tests stay green (uc1 26 / uc2 30 / uc3 32 Python + 19 jest) via an autouse `disable_langfuse` fixture (mocks `get_langfuse`→`None`); ruff/black/isort/mypy --strict (per-package) + check-docs clean. **Restarted all 3 live services** (manual `setsid` uvicorn from the working tree — note the `sentinel-eval`/`sentinel-remote` systemd units are `inactive` and point at empty `/srv/sentinel/*` dirs; the live services actually run from `/home/Fantazy/AINS` and there is no `sentinel-flight` unit) and **verified a live `xqdrant-search` trace landed in Langfuse** (`lf.api.trace.list()`), with span export now 403-free. PREVIOUS: **bolder, branded dashboard pass** (impeccable `bolder` + brand register): adopted the uploaded **`sentinel_logo.svg`** as the recurring hexagon-shield motif (`components/sentinel/Logo.tsx`: themeable `SentinelMark` in the nav, an animated radar-sweep `SentinelEmblem` in the hero, `SentinelLockup` in the footer, `app/icon.svg` favicon, `.hexmesh` texture); swapped the headline face to **Bricolage Grotesque** (offline `@fontsource-variable`, escaping the Geist/Vercel reflex) over Geist Sans body + Geist Mono telemetry; gave it a real "flight-recorder / instrument" POV (new headline "The flight recorder for AI agents.", `.bezel` instrument framing instead of glass, amplified mono stat band, green-tinted near-black neutrals). Critically, **converted every reveal to paint-time CSS** (`motion-safe:animate-fade-up`) after headless-Chromium screenshots caught the hero + inner pages shipping **blank** (content was gated on framer `initial="hidden"` until hydration) — the impeccable "reveal-gated blank content" trap. Re-verified desktop + mobile + verdict screenshots render on paint; `build`/`typecheck`/`lint` green; redeployed. PREVIOUS: **redesigned the dashboard** against the three design skills (`.agents/skills/{emil-design-eng, design-taste-frontend, impeccable}`): a new **mission-control** dark theme (single emerald accent `#34E5B0`; red/amber reserved for real verdict state), **Geist** type via the offline-safe `geist` package (dropped the system-font stack), emil's strong ease-out curves, an aurora+grain hero, and a brand-new **landing home page** (`components/sentinel/views/HomeLanding.tsx`): asymmetric hero with a **real component preview** (`ReliabilityRing` animated pass-rate gauge + live verdict chips, mouse-tilt via `motion.tsx` `Tilt`), a stat band, a connected "one loop, three jobs" pipeline, and a recent-verdicts list. Removed the old `HomeView`/`StatsRow`. Followed the skills' bans (zero em-dashes in visible copy, no gradient text, no AI-purple, no fake screenshots, radius ≤16px) and fixed the impeccable "reveal-gated blank content" trap (counters/rings/sections now default to their real value and animate as enhancement). Verified with headless-Chromium screenshots (desktop + mobile): stat band, loop, and recent-verdicts all render; headline ≤2 lines. `build`/`typecheck`/`lint`/`check-docs` green; redeployed via `sentinel-dashboard`. PREVIOUS (2026-06-20): built **Phase 5 `packages/dashboard`**, the unified Sentinel UI: **Next.js 16** App Router (Turbopack) + React 18.3 + Tailwind + hand-rolled shadcn-style primitives + Framer Motion, dark premium theme. All 5 screens (`/` overview, `/runs`, `/runs/[run_id]` trace, `/verdicts/[run_id]`, `/replay/[run_id]`) + `app/api/{replay,bisect}` server proxies + the 6 spec components (RunStatusBadge/VerdictCard/StepTimeline/DimensionTable/AttributionBox/StatsRow). `lib/api.ts` server-fetches each live service with `?mock=true` support and automatic live→mock fallback (`lib/mock-data.ts` fixtures match the API shapes exactly; `lib/types.ts` mirrors `schema.ts`). Next-16 specifics: `params`/`searchParams` awaited as Promises; ESLint-9 flat config (`eslint.config.mjs`) spreading `eslint-config-next`'s native flat array (Next 16 removed `next lint`); `allowBuilds: {sharp:false, unrs-resolver:false}` in `pnpm-workspace.yaml` to clear the build gate. Added `packages/dashboard` to the pnpm workspace; `pnpm --filter dashboard build` + `typecheck` + `lint` all green. **Deployed on the VM** as the `sentinel-dashboard` systemd unit (`next start -p 3001`, enabled) and exposed at **`https://dashboard.ahmedxsaad.me`** (new `sentinel`-tunnel ingress → `localhost:3001` + proxied DNS CNAME). Split `lib/api.ts` into public link URLs vs internal fetch bases (`FLIGHT_RECORDER_INTERNAL_URL`/`EVAL_ENGINE_INTERNAL_URL` → localhost on the VM), so `/runs` + `/runs/[id]` now serve **LIVE** data (verdict screens stay mock-fallback: eval has no `GET /verdicts`). The zone's Cloudflare managed/bot challenge means `curl` gets `403 cf-mitigated: challenge` while browsers pass — a shell 403 is not an outage. Updated §0 service-URL table, dashboard README/CLAUDE.md, `infra/cloudflare/README.md`, and `infra/azure/setup.sh` (added the `sentinel-dashboard` unit) + Section 11 (Phase 5 in progress: dashboard done + deployed, drift detector remains). PREVIOUS: wired the **Phase 4 end-to-end integration loop** (UC1+UC2+UC3): `POST /analyze` now generates a `run_id`, records every RCA-generation CF Workers AI call into a MinIO cassette via the new `AsyncRecordingTransport` (hash-chain audit → D1), writes a `run_manifests` row (`flight_recorder.manifest.write_run_manifest`), then calls eval-engine `:8000/evaluate {run_id}` and returns `eval_verdict` + `replay_link` on the response. Enriched the cassette with a full-`records` list and pointed `eval_engine.trace_loader` at it (`cassette_store` MinIO read; D1 previews are now fallback only). Added `atlassian_remote.recording`/`eval_client`, a `cf_ai_client` recording contextvar, `EVAL_ENGINE_URL` (+ `.env.example`), `flight-recorder`→atlassian-remote and `boto3`→eval-engine deps, and `tests/integration/test_full_loop.py`. `make test-uc2/uc1/uc3` Python green (30/22/31), mypy --strict + ruff/black/isort + check-docs clean. (TS jest for atlassian-agent unchanged + not re-run: pnpm install blocked by a `minimumReleaseAge` lockfile policy; the `/analyze` field additions are additive-safe for the agent's structural TS contract.) Then **live-validated the loop on the VM** end-to-end (fixing two real bugs the live model exposed: `cf_ai_chat` returning a parsed-JSON dict, and the eval reporter 500-ing when Jira filing failed → now best-effort), reconciled `/srv/sentinel/.env` (AO project key + missing secrets/D1 id), and added `scripts/seed_xqdrant.py` + `make seed-xqdrant` (seeded 101 incidents + 11 runbooks so retrieval works). Then **synced the docs** (2026-06-20): brought every package README/CLAUDE.md in line with the live-validated Phase 4 state, fixed the `packages/README.md` dependency DAG (atlassian-remote→flight-recorder), incorporated the `forge.yml`→`manifest.yml` rename (real app ARI) + all references, corrected the test counts (uc2=30, uc3=32), and fixed `eval_report.md`'s evaluator model to the CF Llama. Earlier: UC3 Phase 3 cores; `AGENTS.md` symlink + `make check-docs`; Phase 1 + Phase 2 cores green.*
