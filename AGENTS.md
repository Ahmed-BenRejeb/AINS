# AGENTS.md — Sentinel: AI Agent Reliability Platform
### Instructions for AI Agents (Claude Code, OpenAI Codex, and others)

> This file mirrors `CLAUDE.md`. Both must stay in sync.
> **Read this file before starting any task. No exceptions.**

---

## Project Overview

**Sentinel** is a unified AI agent reliability platform for the Atlassian ecosystem, built for the AINS Hackathon 2026.

Three use cases, one system:
- **UC2 (Flight Recorder):** captures OTel GenAI traces of every agent run — LLM calls, tool calls, state snapshots
- **UC1 (Eval Engine):** judges those traces using code graders + LLM-as-judge, produces auditable verdicts with failure attribution and drift detection
- **UC3 (Atlassian Agent):** a Rovo Agent on Forge that gets instrumented by UC1+UC2; verdicts are filed as Jira issues

All three share a single OTel `gen_ai.*` trace spine.

---

## Repository Structure

```
sentinel/
├── CLAUDE.md                  ← Claude Code reads this (same content as AGENTS.md)
├── AGENTS.md                  ← You are here (Codex and others read this)
├── Makefile                   ← single source of truth for all commands
├── .env.example               ← environment variable template
│
├── packages/
│   ├── trace-core/            ← shared OTel GenAI schema (Python + TypeScript types)
│   ├── flight-recorder/       ← UC2: HTTP proxy + record/replay/bisect (Python)
│   ├── eval-engine/           ← UC1: graders, judge, drift, verdicts (Python)
│   ├── atlassian-agent/       ← UC3: Forge Rovo Agent + Actions (TypeScript)
│   ├── atlassian-remote/      ← UC3: heavy compute backend via Forge Remote (Python)
│   └── dashboard/             ← shared UI: traces, verdicts, replay (Next.js)
│
├── infra/
│   ├── cloudflare/wrangler.toml
│   └── azure/setup.sh
│
├── scripts/
│   ├── seed_atlassian.py      ← creates 100 synthetic incidents + 20 runbooks
│   └── run_synthetic_eval.py  ← runs eval suite on synthetic data
│
├── spec/                      ← open contribution: OTel + MCP proposals
└── docs/                      ← battle plan, architecture diagram, eval report,technical specifications
```

Each package has its own `CLAUDE.md` with focused context. Read it before working in that package.

---

## Build and Test Commands

```bash
make setup          # install all dependencies
make test           # run all tests — must pass before any commit
make test-uc1       # eval-engine tests only
make test-uc2       # flight-recorder tests only
make test-uc3       # atlassian-remote tests only
make check          # lint + typecheck — must pass before any commit
make lint           # ruff (Python) + eslint (TypeScript)
make format         # black + isort (Python), prettier (TypeScript)
make typecheck      # mypy (Python) + tsc --noEmit (TypeScript)
make seed           # seed Atlassian dev site with synthetic data
make eval           # run the eval suite, output pass^k report
make dev            # start all local development services
make deploy-forge   # deploy Forge app to Atlassian dev environment
make deploy-cf      # deploy Cloudflare Workers + D1 migrations
```

**Before every commit, always run:**
```bash
make check && make test
```
Both must pass with zero errors. No exceptions.

---

## Agent Behavior Rules

### Before Starting Any Task
1. Read `CLAUDE.md` (or this file) to understand current project state
2. Read the `CLAUDE.md` in the relevant package directory
3. Check Section 11 ("Current Status") for which phase is active
4. Check Section 10 ("Known Issues/Gotchas") for relevant warnings

### While Working
- **Respect the file structure.** Never create files outside their designated package. Shared types go in `trace-core/`.
- **Use `make` commands.** Never run raw `python`, `npm`, `pytest` commands — use the `Makefile` aliases.
- **Write tests with code.** Every new function ships with at least one test. Tests are documentation.
- **Use constants, never magic numbers.** Every numeric threshold must be a named constant with a comment.
- **Type everything.** Python: type hints on all signatures. TypeScript: strict mode, no `any`.
- **Write docstrings on every function.** Codex reads these. Another AI must be able to understand the function from its docstring alone.

### Committing
- **Commit at every logical checkpoint** — a passing test, a completed function, a working action
- **Use Conventional Commits format:** `type(scope): description`
  - Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`, `perf`
  - Scopes: `trace-core`, `flight-recorder`, `eval-engine`, `atlassian-agent`, `atlassian-remote`, `dashboard`, `infra`, `spec`
- **Good:** `feat(eval-engine): add position-bias calibration to LLM judge`
- **Bad:** `fix stuff`, `WIP`, `update`, `done`
- Run `make check && make test` before every commit

### After Completing a Task
- **Update `CLAUDE.md`** if any of the following changed:
  - File structure (new modules, files)
  - Architecture decisions (new patterns adopted)
  - Known issues (new gotcha discovered)
  - Commands (new `make` target added)
  - Environment variables (new var required)
  - Status (phase completed or blocked)
- **Mirror changes to `AGENTS.md`** — they must stay in sync
- Update the "Last updated" line at the bottom of both files

---

## Key Architectural Patterns

### 1. OTel GenAI Trace Schema
All agent runs emit `gen_ai.*` spans. The shared schema lives in `packages/trace-core/`.
```python
# Always import trace types from trace-core, never redefine them
from sentinel.trace_core import TraceRecord, RunManifest, TraceKind
```

### 2. Pydantic Structured Outputs (Required for Replay Determinism)
Tool dispatch must always use structured JSON (Pydantic). Never parse tool calls from free text.
```python
class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    confidence: float

# ✅ Right: LLM outputs ToolCall model
# ❌ Wrong: extract tool name from free-text response
```

### 3. Exponential Backoff on All Atlassian API Calls
Atlassian rate limits (65K points/hr, enforced March 2026) return HTTP 429. Always use the shared backoff utility:
```python
from sentinel.atlassian_remote.atlassian_client import api_call_with_backoff
```

### 4. Hash-Chained Audit Records
Every trace record must be written with the audit chain. Use `write_audit_record()` from `flight-recorder`:
```python
from sentinel.flight_recorder.audit.hash_chain import write_audit_record
```

### 5. Environment Variables Only
No hardcoded URLs, tokens, or IDs anywhere in the codebase. All config comes from `.env` via `python-dotenv` or `process.env` in Node.

---

## Coding Standards Summary

**Python:**
- Type hints required on all functions
- Docstring required on all functions (explain what, why, args, returns, raises)
- `ruff` for linting (must pass), `black` for formatting, `mypy` for type checking
- `pytest` for tests, fixtures in `tests/fixtures/`
- 80% minimum line coverage per package

**TypeScript:**
- Strict mode (`"strict": true` in tsconfig)
- JSDoc required on all exported functions
- No `any` without an explanatory comment
- `eslint` + `prettier`, `vitest` for tests

**Universal:**
- No `TODO`/`FIXME` on `main` — create a GitHub Issue instead
- No commented-out code — delete it (git history preserves it)
- No `console.log` in production code — use the structured logger
- All numeric thresholds are named constants with a comment explaining their origin

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Used By | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | eval-engine, atlassian-remote | Main LLM for judging and RCA |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | All CF services | Cloudflare access |
| `CF_D1_DATABASE_ID` | flight-recorder, eval-engine | Trace + verdict storage |
| `ATLASSIAN_SITE` | atlassian-remote, scripts | Your `https://xxx.atlassian.net` URL |
| `ATLASSIAN_API_TOKEN` | atlassian-remote, scripts | Atlassian API token |
| `LANGFUSE_HOST` | All packages (instrumentation) | Self-hosted Langfuse on Azure VM |
| `AUDIT_HMAC_KEY` | flight-recorder | Must be 32+ random chars |
| `FLIGHT_MODE` | flight-recorder | `record` \| `replay` \| `passthrough` |
| `EVAL_CONFIDENCE_THRESHOLD` | eval-engine | Default: `0.70` |

---

## What Good Output Looks Like (Codex Evaluation Criteria)

When Codex reviews this codebase, it will check:
- [ ] Functions have docstrings that explain intent, not just what the code does
- [ ] All type hints are present and correct (mypy passes)
- [ ] Tests exist and cover both happy path and failure cases
- [ ] No magic numbers — only named constants
- [ ] No hardcoded secrets or URLs
- [ ] Conventional commit messages throughout git history
- [ ] CLAUDE.md and AGENTS.md are current (not stale)
- [ ] `make check && make test` passes from a clean checkout
- [ ] The file structure matches what is documented in Section 2

---

## Current Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Foundation | ⬜ Not started | |
| Phase 1 — UC2 Flight Recorder | ⬜ Not started | |
| Phase 2 — UC1 Eval Engine | ⬜ Not started | |
| Phase 3 — UC3 Atlassian Agent | ⬜ Not started | |
| Phase 4 — Integration | ⬜ Not started | |
| Phase 5 — Differentiators | ⬜ Not started | |

---

*Last updated: 17/06/2026 20:01 | Updated by: Ahmed*
*This file mirrors `CLAUDE.md`. Keep them in sync.*
