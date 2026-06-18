# CLAUDE.md — Sentinel: AI Agent Reliability Platform
### ⚠️ READ THIS FILE AT THE START OF EVERY SESSION — NO EXCEPTIONS

> This file is the single source of truth for project context, architecture, and working rules.
> **Update it whenever architecture changes, a gotcha is discovered, or a phase completes.**
> Codex will evaluate your work after each session — write code as if you won't be there to explain it.

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
| xqdrant | internal only | 6333 |
| MinIO S3 | internal only | 9090 |

### Cloudflare Resources
| Resource | Name / ID |
|---|---|
| D1 database | `sentinel-traces` (ID in `/srv/sentinel/.env`) |
| Vectorize index | `sentinel-embeddings` (768-dim, cosine) |
| Workers AI | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (main LLM) |
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
├── AGENTS.md                  ← mirrors this file (Codex-compatible)
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

CF_AI_MODEL_MAIN=@cf/meta/llama-3.3-70b-instruct-fp8-fast
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
make check          # lint + typecheck (run before every commit)
make lint           # ruff (Python) + eslint (TypeScript)
make format         # black + isort (Python), prettier (TypeScript)
make eval           # run eval suite, output pass^k report
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
| Main LLM (RCA, eval judge) | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Free 10k neurons/day |
| Safety pre-filter | `@cf/meta/llama-guard-3-8b` | Fast, cheap |
| Embeddings (768-dim) | `@cf/baai/bge-base-en-v1.5` | For xqdrant + drift |

### Frameworks
| Layer | Choice |
|---|---|
| Agent framework | LangGraph |
| LLM instrumentation | OpenLLMetry (`traceloop-sdk`) |
| Observability UI | Langfuse (self-hosted, running) |
| Forge app (UC3) | Forge TypeScript SDK |
| LLM proxy/intercept | httpx transport override |
| Vector search | xqdrant (Qdrant fork, port 6333) |
| Blob storage | MinIO (S3-compatible, port 9090) — NOT Cloudflare R2 |
| Trace metadata | Cloudflare D1 (SQLite) |
| Dashboard | Next.js 14 + shadcn/ui |

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

---

## 11. Current Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Foundation | ✅ Done | Azure VM, Langfuse, xqdrant, D1, Vectorize, MinIO, Atlassian, 100 incidents seeded |
| Foundation — `trace-core` | ✅ Done | Shared contract complete: constants, Pydantic v2 schemas, hash_utils, OTel GenAI span helpers, schema.ts mirror. `make test-core` green (19 tests); ruff/black/isort/mypy --strict clean on the package |
| Phase 1 — UC2 Flight Recorder | 🟦 In progress | Core built: cassette, RecordingTransport (record/replay/passthrough), @record_tool, hash-chain audit, D1/MinIO clients, replay + bisect, FastAPI on 8001. `make test-uc2` green (27 tests, 88% cov); ruff/black/isort/mypy --strict clean on the package |
| Phase 2 — UC1 Eval Engine | 🟦 In progress | Core built: cf_ai_client, safety pre-filter (Llama Guard), code grader, calibrated LLM judge (mandatory position-bias calibration), DAG failure attribution, pass^k (all() not any()), verdict reporter (files AO Jira issue, type id 10013, no priority/labels), FastAPI on 8000. `make test-uc1` green (19 tests, 74% cov); ruff/black/isort/mypy --strict clean |
| Phase 3 — UC3 Atlassian Agent | ⬜ Not started | Start after trace-core is done |
| Phase 4 — Integration | ⬜ Not started | |
| Phase 5 — Differentiators | ⬜ Not started | |

**⚡ Next task: Phase 3 — UC3 Atlassian Agent, plus UC1/UC2 integration glue.** The UC2 flight-recorder and UC1 eval-engine cores are in place. Remaining cross-cutting work: record a real agent run end-to-end against live MinIO/D1, write `run_manifests` rows, and wire the eval-engine `trace_loader` to the live flight recorder so `POST /evaluate {run_id}` reconstructs full traces. Reuse `normalize_request` / `hash_step_key` from `trace_core` for cassette keys — do not redefine them.

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
> - **Env vars:** new code uses `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` (per §10 gotcha), plus `CF_D1_DATABASE_ID`, `AUDIT_HMAC_KEY`, and the `BLOB_STORAGE_*` set. `.env.example` still lists the older `CF_*` names — reconcile when wiring live.
> - **Storage is mockable:** `storage.minio_client.{store,load}_blob` and `storage.d1_client.insert/query` are module-level functions tests monkeypatch, so the whole record/replay loop runs with zero network. All HTTP in tests is mocked via `pytest-httpx`.
> - **Workspace:** added `packages/flight-recorder` to `[tool.uv.workspace] members`; added `pytest-httpx` + `pytest-cov` to the dev group; added a mypy override ignoring missing stubs for `boto3`/`botocore`/`uvicorn`/`mypy_boto3_s3`.

> **trace-core build notes (18 Jun 2026):**
> - **Layout:** standard src-layout — the importable package is `packages/trace-core/src/trace_core/`, imported as `from trace_core import ...`. No `sentinel.` namespace prefix (it added repetition with the repo name and a nesting level for no benefit). Future Python packages follow the same shape: `packages/<pkg>/src/<pkg>/`, imported as `from <pkg> import ...`.
> - **Workspace:** a root `pyproject.toml` now defines the uv workspace (`make setup` → `uv sync --all-packages`) and the shared tooling config (pytest, mypy --strict + pydantic plugin, ruff, black, isort). Add future Python packages to `[tool.uv.workspace] members`.
> - **`make check` is not yet green repo-wide** — blocked only by items outside trace-core: pre-existing lint errors in `scripts/seed_atlassian.py` + `scripts/run_synthetic_eval.py`, and the TS packages (`atlassian-agent`, `dashboard`) which have no `package.json` yet (Phase 3). trace-core itself passes ruff/black/isort/mypy/pytest.

---

## 12. Evaluation Checklist (Run Before Demo)

- [ ] `make test` passes with zero failures
- [ ] `make check` passes with zero lint/typecheck errors
- [ ] No `.env` values committed to git
- [ ] No `TODO`/`FIXME` comments in `main` branch
- [ ] Every Python function has a docstring
- [ ] Every exported TypeScript function has JSDoc
- [ ] CLAUDE.md and AGENTS.md are in sync
- [ ] `make eval` produces a report with `pass^k` metric
- [ ] End-to-end demo scenario runs without manual intervention

---

*Last updated: 18 June 2026 by Ahmed Saad; Phase 0 + trace-core foundation complete, starting Phase 1*