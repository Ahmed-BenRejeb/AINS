# CLAUDE.md — Sentinel: AI Agent Reliability Platform
### ⚠️ READ THIS FILE AT THE START OF EVERY SESSION — NO EXCEPTIONS

> This file is the single source of truth for project context, architecture, and working rules.
> **Update it whenever architecture changes, a gotcha is discovered, or a phase completes.**
> Codex will evaluate your work after each session — write code as if you won't be there to explain it.

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

**Reference documents:**
- Technical specs document of the hackathon : `docs/TECHNICAL_SPECS.md`
- Full technical battle plan: `docs/BATTLE_PLAN.md`
- Architecture diagram: `docs/ARCHITECTURE.md`
- OTel extension spec: `spec/otel-genai-replay-extension.md`
- MCP audit spec: `spec/mcp-audit-trail-proposal.md`
---

## 2. Monorepo Structure

```
sentinel/
├── CLAUDE.md                  ← YOU ARE HERE — read first every session
├── AGENTS.md                  ← mirrors this file (Codex-compatible)
├── Makefile                   ← all commands live here, use make <cmd>
├── .env.example               ← copy to .env, never commit .env
│
├── packages/
│   ├── trace-core/            ← shared OTel GenAI schema + types (Python + TS)
│   │   └── CLAUDE.md          ← read this when working in this package
│   ├── flight-recorder/       ← UC2: HTTP proxy, record/replay/bisect/inject (Python)
│   │   └── CLAUDE.md
│   ├── eval-engine/           ← UC1: graders, judge, drift, verdicts (Python)
│   │   └── CLAUDE.md
│   ├── atlassian-agent/       ← UC3: Forge app — Rovo Agent + actions (TypeScript)
│   │   └── CLAUDE.md
│   ├── atlassian-remote/      ← UC3: heavy compute backend via Forge Remote (Python)
│   │   └── CLAUDE.md
│   └── dashboard/             ← shared UI: traces, verdicts, replay (Next.js)
│       └── CLAUDE.md
│
├── infra/
│   ├── cloudflare/
│   │   └── wrangler.toml      ← D1, R2, Vectorize, Queues, Workers config
│   └── azure/
│       └── setup.sh           ← VM provisioning script
│
├── scripts/
│   ├── seed_atlassian.py      ← seeds dev site with 100 synthetic incidents + runbooks
│   └── run_synthetic_eval.py  ← runs the eval suite on synthetic data
│
├── spec/                      ← open contribution artifacts (bonus points)
│   ├── otel-genai-replay-extension.md
│   └── mcp-audit-trail-proposal.md
│
├── docs/
│   ├── TECHNICAL_SPECS.md
│   ├── BATTLE_PLAN.md
│   └── ARCHITECTURE.md
│
└── tests/                     ← integration tests that span packages
    └── e2e/
```

### File Structure Rules — ENFORCED
- ✅ New modules go in their designated package directory
- ✅ Shared types/schemas go in `packages/trace-core/` — never duplicate them
- ✅ Scripts (one-off, seeding, eval runs) go in `scripts/`
- ✅ Spec/proposal documents go in `spec/`
- ❌ Never create files at the root level unless they are config files (`.env`, `Makefile`, etc.)
- ❌ Never put Python code in the Forge TypeScript package and vice versa
- ❌ Never hardcode values that belong in `.env`

---

## 3. Environment Variables

Copy `.env.example` to `.env`. Never commit `.env`.

```bash
# ── Anthropic ─────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Cloudflare ────────────────────────────────────────────────
CF_ACCOUNT_ID=...
CF_API_TOKEN=...
CF_D1_DATABASE_ID=...
CF_R2_BUCKET=sentinel-cassettes
CF_VECTORIZE_INDEX=sentinel-embeddings

# ── Atlassian ─────────────────────────────────────────────────
ATLASSIAN_SITE=https://your-site.atlassian.net
ATLASSIAN_EMAIL=your@email.com
ATLASSIAN_API_TOKEN=...
ATLASSIAN_JSM_SERVICE_DESK_ID=...
ATLASSIAN_JIRA_PROJECT_KEY=SENT

# ── Langfuse (self-hosted on Azure VM) ────────────────────────
LANGFUSE_HOST=https://langfuse.yourteamdomain.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# ── Forge Remote (Azure VM endpoint) ─────────────────────────
FORGE_REMOTE_URL=https://remote.yourteamdomain.com
FORGE_REMOTE_SECRET=...

# ── Audit ─────────────────────────────────────────────────────
AUDIT_HMAC_KEY=...   # used for hash-chained audit receipts — must be random, 32+ chars

# ── App Config ────────────────────────────────────────────────
FLIGHT_MODE=record   # "record" | "replay" | "passthrough"
EVAL_CONFIDENCE_THRESHOLD=0.70
LOG_LEVEL=INFO
```

---

## 4. Commands (always use `make`, never remember raw commands)

```bash
# ── Setup ────────────────────────────────────────────────────
make setup          # install all dependencies (Python + Node)
make env            # copy .env.example to .env (run once)

# ── Development ───────────────────────────────────────────────
make dev            # start all local services (tunnel, eval api, remote api)
make tunnel         # start Cloudflare Tunnel only
make langfuse       # open Langfuse UI in browser

# ── Testing ───────────────────────────────────────────────────
make test           # run ALL tests across all packages
make test-core      # packages/trace-core tests
make test-uc1       # packages/eval-engine tests
make test-uc2       # packages/flight-recorder tests
make test-uc3       # packages/atlassian-remote tests
make test-e2e       # end-to-end integration tests

# ── Code Quality ──────────────────────────────────────────────
make lint           # run ruff (Python) + eslint (TS) across all packages
make format         # auto-format: black + isort (Python), prettier (TS)
make typecheck      # mypy (Python) + tsc --noEmit (TypeScript)
make check          # lint + typecheck (run before every commit)

# ── Data & Eval ───────────────────────────────────────────────
make seed           # seed Atlassian dev site with synthetic data
make eval           # run the eval suite (pass^k report)
make eval-report    # generate the evaluation report PDF

# ── Deployment ────────────────────────────────────────────────
make deploy-cf      # deploy Cloudflare Workers + D1 migrations
make deploy-forge   # deploy Forge app to Atlassian dev environment
make deploy-remote  # deploy Forge Remote backend to Azure VM

# ── Utilities ─────────────────────────────────────────────────
make clean          # remove build artifacts, __pycache__, .next
make logs           # tail logs from all services
make status         # show status of all services + Cloudflare resources
```

---

## 5. Coding Standards

### Python (eval-engine, flight-recorder, trace-core, atlassian-remote)

```python
# ✅ Required: type hints on all function signatures
def evaluate_run(run_id: str, k: int = 8) -> EvalVerdict:
    ...

# ✅ Required: docstrings on every function (Codex will read these)
def evaluate_run(run_id: str, k: int = 8) -> EvalVerdict:
    """
    Evaluate a single agent run at multiple levels.
    
    Args:
        run_id: The UUID of the recorded run to evaluate.
        k: Number of independent trials for pass^k calculation.
    
    Returns:
        EvalVerdict with overall score, per-dimension scores,
        failure attribution, and self-evaluation confidence.
    
    Raises:
        RunNotFoundError: If run_id does not exist in D1.
    """

# ✅ Required: Pydantic models for all data structures
from pydantic import BaseModel

class EvalVerdict(BaseModel):
    run_id: str
    verdict: Literal["pass", "fail", "uncertain"]
    confidence: float
    ...

# ✅ Required: named constants, never magic numbers
CONFIDENCE_THRESHOLD = 0.70       # minimum confidence to auto-post to Jira
MAX_RETRIEVAL_RESULTS = 5         # top-k for vector search
PASS_AT_K_TRIALS = 8             # k for pass^k metric (τ-bench standard)

# ❌ Never do this
if confidence > 0.7:  # what is 0.7? why?
    post_to_jira()
```

**Python tooling:** `ruff` for linting, `black` for formatting, `isort` for imports, `mypy` for type checking, `pytest` for tests.

### TypeScript (atlassian-agent, dashboard)

```typescript
// ✅ Required: strict TypeScript, no `any`
// tsconfig.json must have "strict": true

// ✅ Required: JSDoc on all exported functions
/**
 * Fetches incident details from JSM and normalizes them into our schema.
 * @param incidentKey - The Jira issue key (e.g., "OPS-42")
 * @param context - Forge request context containing principal.accountId
 * @returns Normalized incident object ready for embedding
 */
export async function fetchIncident(
  incidentKey: string,
  context: ForgeContext
): Promise<NormalizedIncident> {
  ...
}

// ✅ Required: explicit return types on all functions
// ❌ Never: implicit any, type assertions without comment
```

**TypeScript tooling:** `eslint` with `@typescript-eslint`, `prettier` for formatting, `vitest` for tests.

### Universal Rules

- **No `TODO` or `FIXME` in commits to `main`** — create a GitHub Issue instead
- **No hardcoded URLs, tokens, or IDs** — everything goes in `.env`
- **No `console.log` left in production code** — use the structured logger
- **No commented-out code** — delete it; git history preserves it
- **Explicit over implicit** — if you're not sure a reader will understand it, add a comment

---

## 6. Git Workflow

### Branch Naming
```
feat/uc1-eval-engine-code-grader
feat/uc2-http-proxy-intercept
feat/uc3-rovo-agent-fetch-incident
fix/replay-bisect-hash-mismatch
chore/seed-synthetic-incidents
docs/update-otel-spec
test/eval-engine-position-bias
```

### Commit Format — Conventional Commits (ENFORCED)
```
<type>(<scope>): <short description in imperative mood>

[optional body — explain WHY, not WHAT]

[optional footer — Refs #issue]
```

**Types:**
| Type | When to use |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `test` | Adding or fixing tests |
| `refactor` | Code change that doesn't add feature or fix bug |
| `chore` | Tooling, deps, config, build |
| `docs` | Documentation only |
| `perf` | Performance improvement |

**Scopes:** `trace-core`, `flight-recorder`, `eval-engine`, `atlassian-agent`, `atlassian-remote`, `dashboard`, `infra`, `spec`

**Examples:**
```bash
# ✅ Good commits
git commit -m "feat(eval-engine): add position-bias calibration to LLM judge"
git commit -m "feat(flight-recorder): implement httpx transport override for LLM interception"
git commit -m "fix(atlassian-agent): handle JSM 429 rate limit with exponential backoff"
git commit -m "test(eval-engine): add pass^k metric test with 8 synthetic trials"
git commit -m "chore(infra): add wrangler.toml for D1 and Vectorize configuration"
git commit -m "docs(spec): draft otel-genai-replay-extension proposal"

# ❌ Bad commits (never do these)
git commit -m "fix stuff"
git commit -m "WIP"
git commit -m "asdfgh"
git commit -m "update"
git commit -m "done"
```

### Commit Frequency Rules
- **Commit at every logical checkpoint** — not just at the end of a session
- A "logical checkpoint" = a passing test, a working function, a completed action
- Committing frequently = smaller diffs = easier Codex review = easier debugging
- **Rule of thumb:** if you've written more than ~50 lines since your last commit, commit now

### Branch Rules
- `main` = always deployable, never commit directly
- Work on feature branches, open a PR to merge
- **Never force-push to `main`**
- Squash commits when merging if there are more than 5 WIP commits

---

## 7. Testing Protocol

### The Rule: Tests Come With Code, Not After

Every new function ships with at least one test. No exceptions. Tests are also documentation — Codex reads them to understand intent.

### Test Structure Per Package
```
packages/eval-engine/
├── src/
│   ├── graders/
│   │   ├── code_grader.py
│   │   └── llm_judge.py
└── tests/
    ├── unit/
    │   ├── test_code_grader.py      # test individual functions in isolation
    │   └── test_llm_judge.py
    ├── integration/
    │   └── test_eval_pipeline.py   # test the full eval pipeline end-to-end
    └── fixtures/
        ├── sample_trace_pass.json  # a trace that should pass
        └── sample_trace_fail.json  # a trace that should fail + expected attribution
```

### What to Test

| Layer | What to Test |
|---|---|
| `trace-core` | Schema validation, serialization/deserialization, hash-chain integrity |
| `flight-recorder` | Record correctly, replay returns recorded response (not live), bisect finds right step |
| `eval-engine` | Code grader catches known failures, judge produces expected verdict on fixtures, pass^k calculates correctly |
| `atlassian-remote` | Embedding + vector search returns relevant results, RCA draft is structured correctly |
| `atlassian-agent` | Actions return correct structure, rate limit backoff triggers correctly |
| `e2e` | Full incident → agent run → flight recorder captures → eval produces verdict → Jira issue filed |

### Before Every Commit
```bash
make check   # lint + typecheck — must pass with zero errors
make test    # all tests — must pass, no skips in the scope you changed
```

### Minimum Coverage
- Unit tests: **80% line coverage** per package
- Integration tests: at least one per major workflow
- E2E tests: at least one full happy path + one failure case

---

## 8. How to Keep This File Updated

**When to update CLAUDE.md (and mirror in AGENTS.md):**

| Event | What to Update |
|---|---|
| Add a new module or package | Section 2 (File Structure) |
| Change a key architectural pattern | Section 9 (Architecture Decisions Log) |
| Discover a gotcha or non-obvious issue | Section 10 (Known Issues/Gotchas) |
| Add a new `make` command | Section 4 (Commands) |
| Add a new environment variable | Section 3 (Environment Variables) |
| Complete a phase | Section 11 (Current Status) |
| A pattern becomes the team standard | Section 5 (Coding Standards) |

**When to update:** at the end of the session that introduces the change, before the final commit.

**AGENTS.md mirrors this file.** After updating CLAUDE.md, copy the changes to AGENTS.md. They must stay in sync.

**Rule:** CLAUDE.md must never be more than one working session out of date.

---

## 9. Architecture Decisions Log

> Record significant decisions here so future sessions (and Codex) understand *why*, not just *what*.

| Date | Decision | Rationale |
|---|---|---|
| Init | Use OTel GenAI `gen_ai.*` spans as the shared trace format | Industry standard (Anthropic, Google, Datadog), positions our replay extension as a real protocol contribution |
| Init | httpx transport override for LLM interception (not mitmproxy) | No separate proxy process; works inside Python SDK without network config |
| Init | Pydantic structured outputs for all tool calls | Required for deterministic replay (AgentRR insight); makes replay match-key calculation reliable |
| Init | Cloudflare D1 + R2 for trace storage (not Postgres) | Serverless, no infra to manage at hackathon scale; D1 for indexed metadata, R2 for large blobs |
| Init | Langfuse self-hosted on Azure VM (not cloud) | MIT license, OTel-native, stays under our control; cloud tier has request limits |
| Init | AGENTS.md mirrors CLAUDE.md | Codex evaluates via AGENTS.md; must stay in sync |

---

## 10. Known Issues / Gotchas

> Add anything non-obvious here so the next session doesn't waste time re-discovering it.

| Issue | Context | Solution/Workaround |
|---|---|---|
| JSM pagination differs from Jira | JSM uses `start`/`limit`, Jira uses `startAt`/`maxResults` | Always use the correct param per API; mixing silently truncates results |
| Atlassian rate limits (March 2026) | Points-based, 65K/hr global pool, returns 429 with `Retry-After` | `api_call_with_backoff()` in `packages/atlassian-remote/src/atlassian_client.py` |
| OTel GenAI conventions are experimental | Must opt in: `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` | Set in `.env` and in `Makefile` dev command |
| Forge sandbox has compute limits | Heavy embedding/LLM work can't run inside Forge | Route via Forge Remote to Azure VM (`FORGE_REMOTE_URL`) |
| Rovo agents: limited cross-product access | A Jira Rovo agent can't auto-read Confluence pages | Must explicitly call `search-runbooks` Action which hits our remote endpoint |
| Cassette replay breaks on ephemeral values | Timestamps, UUIDs in prompts cause cassette miss on replay | Normalize ephemeral values out of the match key in `flight_recorder/proxy/cassette.py` |

---

## 11. Current Status

> Update this section at the end of every session.

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Foundation | ⬜ Not started | Azure VM, Langfuse, CF infra, Atlassian dev site |
| Phase 1 — UC2 Flight Recorder | ⬜ Not started | HTTP proxy, record/replay |
| Phase 2 — UC1 Eval Engine | ⬜ Not started | Code grader, LLM judge, verdicts |
| Phase 3 — UC3 Atlassian Agent | ⬜ Not started | Forge Rovo agent, Forge Remote |
| Phase 4 — Integration | ⬜ Not started | Wire UC3 into UC1+UC2, close the loop |
| Phase 5 — Differentiators | ⬜ Not started | Self-eval, spec docs, demo polish |

**Status legend:** ⬜ Not started | 🔄 In progress | ✅ Done | ❌ Blocked (add reason)

**Current blockers:** *(none — project not started)*

**Next session priorities:**
1. Phase 0: provision Azure VM and deploy Langfuse
2. Phase 0: `wrangler` setup for D1 + R2 + Vectorize
3. Phase 0: create Atlassian free dev site and verify API access

---

## 12. Evaluation Checklist (Run Before Demo)

Before the final demo, verify every item below:

- [ ] `make test` passes with zero failures
- [ ] `make check` passes with zero lint/typecheck errors
- [ ] No `.env` values committed to git
- [ ] No `TODO`/`FIXME` comments in `main` branch
- [ ] Every function in Python has a docstring
- [ ] Every exported function in TypeScript has JSDoc
- [ ] CLAUDE.md and AGENTS.md are in sync
- [ ] `make seed` runs clean against the dev site
- [ ] `make eval` produces a report with `pass^k` metric
- [ ] The end-to-end demo scenario runs without manual intervention
- [ ] Architecture diagram in `docs/ARCHITECTURE.md` matches the real system
- [ ] `/spec` documents are finalized and presentable
- [ ] Evaluation report (`docs/eval_report.md`) is complete

---

*Last updated: 17/06/2026 20:01 | Updated by: Ahmed*
