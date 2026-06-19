# AGENTS.md — Sentinel: AI Agent Reliability Platform
### Instructions for AI Agents (Claude Code, OpenAI Codex, and others)

> This file mirrors `CLAUDE.md`. Both must stay in sync.
> **Read this file before starting any task. No exceptions.**
>
> **📝 Update log rule (required):** whenever you edit this file (or `CLAUDE.md`), update the
> **_Last updated_** line at the bottom of both with the **exact timestamp** (`YYYY-MM-DD HH:MM TZ`),
> **the name of who/what made the change**, and a one-line summary.

---

## Project Overview

**Sentinel** is a unified AI agent reliability platform for the Atlassian ecosystem.
**Repo:** `https://github.com/ahmedxsaad/AINS`
**Team:** Ahmed Saad, Moetez Fradi, Ahmed Ben Rejeb (Team Selecao)

Three use cases, one OTel GenAI trace spine:
- **UC2 (Flight Recorder):** captures every LLM call and tool call
- **UC1 (Eval Engine):** judges traces, produces auditable verdicts
- **UC3 (Atlassian Agent):** Rovo Agent on Forge, instrumented by UC1+UC2

---

## DEPLOYED INFRASTRUCTURE (use these exact values)

```
Azure VM:  48.220.48.34  user: Fantazy

Services:
  langfuse.ahmedxsaad.me  → Langfuse UI (port 3000)
  eval.ahmedxsaad.me      → Eval Engine API (port 8000)
  remote.ahmedxsaad.me    → Forge Remote API (port 8080)
  flight.ahmedxsaad.me    → Flight Recorder API (port 8001)
  localhost:6333          → xqdrant (INTERNAL ONLY)
  localhost:9090          → MinIO S3 (INTERNAL ONLY)

Cloudflare:
  D1 database:  sentinel-traces (ID in /srv/sentinel/.env)
  Vectorize:    sentinel-embeddings (768-dim, cosine)
  Workers AI:   @cf/meta/llama-3.3-70b-instruct-fp8-fast (main LLM)
                @cf/meta/llama-guard-3-8b (safety)
                @cf/baai/bge-base-en-v1.5 (embeddings)

Atlassian:
  Site:               https://ahmedains.atlassian.net
  JSM project key:    AO
  Service desk ID:    1
  Incident type ID:   10013  ← use ID not name, name is [System] Incident
  Confluence space:   SENT
  Incidents seeded:   100 (AO project)
  Runbooks seeded:    10 (SENT space)

Blob Storage (MinIO — NOT R2, no credit card):
  Endpoint:    http://localhost:9090
  Bucket:      sentinel-cassettes
  Access key:  minio
  Secret key:  <see /srv/sentinel/.env>
```

---

## Build and Test Commands

```bash
make test           # run all tests — must pass before any commit
make check          # lint + typecheck — must pass before any commit
make test-uc1       # eval-engine tests
make test-uc2       # flight-recorder tests
make test-uc3       # atlassian-remote + atlassian-agent tests
make lint           # ruff (Python) + eslint (TypeScript)
make format         # black + isort (Python), prettier (TypeScript)
make eval           # run eval suite, output pass^k report
make deploy-forge   # deploy Forge app
make deploy-remote  # deploy to Azure VM
```

**Before every commit:** `make check && make test`

---

## LLM Calls — CF Workers AI Pattern (NO Anthropic SDK)

```python
import httpx, os

async def cf_ai_chat(messages: list[dict], model: str = None) -> str:
    model = model or os.environ["CF_AI_MODEL_MAIN"]
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": messages, "max_tokens": 1000},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["result"]["response"]

async def cf_ai_embed(texts: list[str]) -> list[list[float]]:
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/baai/bge-base-en-v1.5",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": texts},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["result"]["data"]
```

---

## Repository Structure

```
AINS/
├── packages/
│   ├── trace-core/          # Shared OTel GenAI schema — START HERE
│   ├── flight-recorder/     # UC2: HTTP proxy, record/replay/bisect (Python)
│   ├── eval-engine/         # UC1: graders, LLM judge, drift (Python)
│   ├── atlassian-agent/     # UC3: Forge Rovo Agent (TypeScript)
│   ├── atlassian-remote/    # UC3: CF Workers AI + xqdrant backend (Python)
│   └── dashboard/           # Shared UI (Next.js)
├── infra/cloudflare/        # wrangler.toml
├── infra/azure/             # VM setup
├── scripts/                 # seed_atlassian.py (ALREADY RUN), run_synthetic_eval.py
├── spec/                    # Protocol gap proposals
└── docs/                    # Battle plan, architecture, eval report
```

---

## Agent Behavior Rules

### Before Starting Any Task
1. Read `CLAUDE.md` Section 0 (deployed infrastructure values)
2. Read the `CLAUDE.md` in the relevant package directory
3. Check Section 11 (current status) for active phase
4. Check Section 10 (known gotchas) for relevant warnings

### While Working
- Use `make` commands — never raw `python`, `npm`, `pytest`
- Write tests with code — every function ships with at least one test
- Use constants, never magic numbers
- All LLM calls use CF Workers AI pattern above — never Anthropic SDK
- Blob storage uses MinIO via boto3 with `endpoint_url=http://localhost:9090`
- xqdrant is at `http://localhost:6333` — never expose externally
- Atlassian issue creation: always use `{"id": "10013"}` for Incident type

### Committing
- Conventional Commits: `type(scope): description`
- Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`
- Scopes: `trace-core`, `flight-recorder`, `eval-engine`, `atlassian-agent`, `atlassian-remote`, `dashboard`
- Run `make check && make test` before every commit

### After Completing a Task
- Update `CLAUDE.md` if architecture, commands, or gotchas changed
- Mirror changes to `AGENTS.md`
- Update Section 11 (current status)

---

## Key Architectural Patterns

### 1. OTel GenAI Trace Schema
```python
from trace_core import TraceRecord, EvalVerdict, AuditBlock
# Never redefine these — import from trace-core
```

### 2. Pydantic Structured Outputs (required for replay determinism)
```python
class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
# Never parse tool calls from free text
```

### 3. Atlassian API — Always Backoff on 429
```python
from atlassian_remote.atlassian_client import api_call_with_backoff
# Rate limit: 65K points/hr (enforced March 2026)
```

### 4. Atlassian Issue Creation — Use Issue Type ID
```python
# CORRECT — use ID
"issuetype": {"id": "10013"}
# WRONG — name rejected by AO JSM project
"issuetype": {"name": "Incident"}
# Also: do NOT include "priority" or "labels" fields for AO project
```

### 5. MinIO Blob Storage
```python
import boto3
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["BLOB_STORAGE_ENDPOINT"],
    aws_access_key_id=os.environ["BLOB_STORAGE_ACCESS_KEY"],
    aws_secret_access_key=os.environ["BLOB_STORAGE_SECRET_KEY"],
)
# bucket: sentinel-cassettes
```

---

## Current Status

| Phase | Status |
|---|---|
| Phase 0 — Foundation | ✅ Complete |
| Foundation — `trace-core` | ✅ Complete |
| Phase 1 — UC2 Flight Recorder | 🟦 In progress |
| Phase 2 — UC1 Eval Engine | 🟦 In progress |
| Phase 3 — UC3 Atlassian Agent | ⬜ Not started |
| Phase 4 — Integration | ⬜ Not started |
| Phase 5 — Differentiators | ⬜ Not started |

`trace-core` is the shared contract for all packages: constants, Pydantic v2 schemas,
hash utils, OTel GenAI span helpers, and a `schema.ts` mirror. `make test-core` is
green (19 tests); ruff/black/isort/mypy --strict pass on the package.

- **Layout:** standard src-layout at `packages/trace-core/src/trace_core/`;
  import as `from trace_core import TraceRecord, EvalVerdict, PASS_AT_K_TRIALS`
  (no `sentinel.` namespace prefix). Future packages follow `packages/<pkg>/src/<pkg>/`.
- **Workspace:** root `pyproject.toml` defines the uv workspace + shared tooling config.
  `make setup` runs `uv sync --all-packages`.
- **Repo-wide `make check` is not yet green** — blocked only by out-of-scope items:
  pre-existing `scripts/` lint errors and the TS packages (no `package.json` yet, Phase 3).

**⚡ flight-recorder core is built** — `packages/flight-recorder/src/flight_recorder/`
(src-layout, imported as `from flight_recorder.proxy.cassette import ...`; `api.py` at the
package root runs on port 8001). Cassette + `RecordingTransport` (record/replay/passthrough,
`FLIGHT_MODE`-driven) + `@record_tool` + hash-chained HMAC audit + D1/MinIO clients + replay
and bisect engines, all reusing `trace_core.normalize_request`/`hash_step_key`. `make test-uc2`
is green (27 tests, 88% cov); ruff/black/isort/mypy --strict pass on the package.

**⚡ eval-engine core is built** — `packages/eval-engine/src/eval_engine/`
(src-layout, imported as `from eval_engine.graders.code_grader import ...`; `api.py` at the
package root runs on port 8000). Safety pre-filter (Llama Guard) → deterministic code grader →
`calibrated_judge` (mandatory position-bias calibration; flip → `uncertain` + `flag_for_human`)
→ DAG failure attribution → `EvalVerdict` with self-evaluation. `pass^k` uses `all()` not `any()`.
Verdict reporter files an AO Jira Incident on fail/flag (issue-type id `10013`, no priority/labels).
All CF Workers AI calls go through `cf_ai_client` and are mocked in tests. `make test-uc1` green
(19 tests, 74% cov); ruff/black/isort/mypy --strict pass.

> **Tooling note:** `make typecheck` now runs mypy **per package** — one recursive
> `mypy packages/` collides on the duplicate root-level `api.py`/`conftest.py` module names.

**⚡ Next: Phase 3 — UC3 Atlassian Agent + UC1/UC2 live integration.**

---

*Last updated: 2026-06-19 06:25 CET by Ahmed Saad (via Claude Code) — reconciled `.env.example` to the code + ran `pip-audit` (no CVEs). Earlier: reconciled README/CLAUDE + docs to the deployed stack; security TODOs live in `CLAUDE.md` §13. Phase 1 + Phase 2 cores built.*
*| Mirrors CLAUDE.md*