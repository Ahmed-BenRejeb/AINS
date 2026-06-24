# Sentinel — System Architecture

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ATLASSIAN CLOUD                                     │
│                                                                             │
│   JSM Incident (webhook trigger)                                            │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────┐                  │
│   │         packages/atlassian-agent  (Forge)           │                  │
│   │         TypeScript · Rovo Agent + Actions           │                  │
│   │                                                     │                  │
│   │  fetch-incident → search-similar → search-runbooks  │                  │
│   │  post-rca-comment → draft-pir-page                  │                  │
│   └──────────────────────┬──────────────────────────────┘                  │
│                          │ Forge Remote HTTP                                │
└──────────────────────────┼─────────────────────────────────────────────────┘
                           │
                ┌──────────▼──────────────────────────────────────────────┐
                │                   AZURE VM                              │
                │         (exposed via Cloudflare Tunnel)                 │
                │                                                         │
                │  ┌──────────────────────────────────────────────────┐   │
                │  │   packages/atlassian-remote  (Python / FastAPI)  │   │
                │  │                                                  │   │
                │  │   /analyze → embed → vector search → RCA draft  │   │
                │  │   /search  → Cloudflare Vectorize query          │   │
                │  │   /embed   → Cloudflare Workers AI               │   │
                │  └──────────────────┬───────────────────────────────┘   │
                │                     │ instruments                        │
                │                     ▼                                    │
                │  ┌──────────────────────────────────────────────────┐   │
                │  │   packages/flight-recorder  (Python)             │   │
                │  │                                                  │   │
                │  │   LLM Proxy → intercept → record gen_ai.* spans  │   │
                │  │   Tool Interceptor → record tool calls           │   │
                │  │   Audit Chain → hash-chained HMAC receipts       │   │
                │  │   Replay Engine → deterministic re-execution     │   │
                │  │   Bisect Engine → find first diverging step      │   │
                │  └──────────────────┬───────────────────────────────┘   │
                │                     │ OTel GenAI traces                  │
                │                     ▼                                    │
                │  ┌──────────────────────────────────────────────────┐   │
                │  │   packages/eval-engine  (Python / FastAPI)       │   │
                │  │                                                  │   │
                │  │   Code Grader → schema, tool-call, outcome check │   │
                │  │   LLM Judge  → rubric scoring, bias calibration  │   │
                │  │   Safety Filter → Llama Guard 3 (Workers AI)     │   │
                │  │   DAG Attributor → per-step failure probability  │   │
                │  │   Drift Detector → distributional shift over time│   │
                │  │   pass^k Metric  → k=8 reliability score        │   │
                │  └──────────────────┬───────────────────────────────┘   │
                │                     │ verdicts + traces                  │
                │  ┌──────────────────▼───────────────────────────────┐   │
                │  │   Langfuse (self-hosted)                         │   │
                │  │   Trace UI · Eval storage · OTel ingest          │   │
                │  └──────────────────────────────────────────────────┘   │
                └─────────────────────────────────────────────────────────┘
                           │
               ┌───────────┼───────────────────────────────────┐
               │           │ CLOUDFLARE                         │
               │           │                                    │
               │   ┌───────▼──────┐  ┌──────────┐  ┌────────┐ │
               │   │  D1 (SQLite) │  │  R2      │  │Vectorize│ │
               │   │  trace meta  │  │  blobs   │  │embeddings│ │
               │   │  verdicts    │  │  cassettes│  │incidents │ │
               │   └──────────────┘  └──────────┘  │runbooks │ │
               │                                    └────────┘ │
               │   ┌──────────────┐  ┌──────────┐             │
               │   │ Workers AI   │  │  Queues  │             │
               │   │ Llama Guard 3│  │  async   │             │
               │   │ BGE-Base-EN  │  │  eval    │             │
               │   └──────────────┘  └──────────┘             │
               └───────────────────────────────────────────────┘
                           │
               ┌───────────▼───────────────────────────────────┐
               │   packages/dashboard  (Next.js — https://dashboard.ahmedxsaad.me) │
               │                                                               │
               │   /              → overview: stats, recent verdicts           │
               │   /runs          → recorded runs list                         │
               │   /runs/[id]     → execution trace (step timeline)            │
               │   /verdicts/[id] → verdict detail + attribution               │
               │   /replay/[id]   → replay + mid-replay inject + bisect        │
               │   /reliability   → drift detection + evaluator quality (κ)    │
               └───────────────────────────────────────────────────────────────┘
```

---

> **Current stack (the ASCII boxes above reflect the original plan — actual differs as noted).**
> All LLM, embedding, and safety calls go through **Cloudflare Workers AI** — there is no
> Anthropic/Claude usage. The main model is **`@cf/meta/llama-3.1-8b-instruct-fp8-fast`**
> (RCA + judge), not Llama 3.3 70B. Trace blobs & cassettes live in **MinIO** on the Azure VM,
> **not Cloudflare R2**. Similarity search uses **xqdrant** (`localhost:6333`), **not Vectorize**.
> **Cloudflare Queues** were skipped — evaluation runs synchronously. The **drift detector is
> built and live** (`POST /drift`, `detect_drift` in eval-engine). Root `CLAUDE.md` §0 / §9 is
> authoritative.

## Data Flow: New Incident → End-to-End

```
1. New JSM incident created
        │
        ▼
2. Atlassian webhook fires → atlassian-agent (Forge) receives it
        │
        ▼
3. Agent calls fetch-incident Action
   → fetches full incident from JSM REST API
        │
        ▼
4. Agent calls search-similar-incidents + search-runbooks Actions
   → Forge Remote → atlassian-remote → Cloudflare Vectorize
   → returns top-k similar past incidents + relevant runbook pages
        │
        ▼
5. atlassian-remote calls the LLM (CF Workers AI — llama-3.1-8b-instruct-fp8-fast)
   → generates structured RcaDraft (Pydantic model, never free text)
   → flight-recorder intercepts this LLM call → records gen_ai.* span
        │
        ▼
6. atlassian-remote calls eval-engine /evaluate
   → eval-engine judges the RcaDraft:
       code grader: schema valid? fields present?
       LLM judge:   correctness, evidence quality, severity rationale
       self-eval:   confidence score + self-critique
   → if confidence < 0.70 → flag_for_human = true
        │
        ├─ confidence OK ──────────────────────────────────────────┐
        │                                                          ▼
        │                                           7a. post-rca-comment → Jira
        │                                           7b. draft-pir-page  → Confluence
        │
        └─ confidence LOW ─────────────────────────────────────────┐
                                                                   ▼
                                              7c. create "needs human review" Jira issue
                                                  with draft RCA attached
        │
        ▼
8. EvalVerdict stored → Cloudflare D1
   Trace (gen_ai.* spans) → Langfuse + D1 (metadata) / MinIO (blobs + cassettes)
   Dashboard updated in real-time
```

---

## Package Dependency Graph

```
                    ┌─────────────────┐
                    │   trace-core    │  ← imported by all, imports nothing
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐
  │flight-recorder│  │ eval-engine  │  │ atlassian-remote    │
  └──────────────┘  └──────────────┘  └─────────────────────┘
          │                                      ▲
          │ OTel traces                          │ Forge Remote HTTP
          ▼                                      │
  ┌──────────────┐                    ┌──────────────────────┐
  │   Langfuse   │                    │  atlassian-agent     │
  └──────────────┘                    │  (TypeScript/Forge)  │
                                      └──────────────────────┘
                                               │
                                               ▼
                                    ┌──────────────────────┐
                                    │     dashboard        │
                                    │    (Next.js)         │
                                    └──────────────────────┘
```

**Rules:** No cycles. `trace-core` has zero local imports. `atlassian-agent` never imports Python packages — it calls `atlassian-remote` via HTTP only.

---

## Deployment Targets

| Package | Language | Deployed On | How |
|---|---|---|---|
| `trace-core` | Python + TS | Imported (not deployed) | uv workspace member (`from trace_core import ...`) / npm |
| `flight-recorder` | Python | Azure VM | systemd service, port 8001 |
| `eval-engine` | Python | Azure VM | systemd service, port 8000 |
| `atlassian-agent` | TypeScript | Atlassian (Forge) | `forge deploy` |
| `atlassian-remote` | Python | Azure VM | systemd service, port 8080 |
| `dashboard` | TypeScript | Azure VM | `sentinel-dashboard` systemd unit (`next start -p 3001`) |

All Azure VM services are exposed externally via **Cloudflare Tunnel** only. The VM has no open ports except SSH (22).

---

## External Services

| Service | Provider | Used For |
|---|---|---|
| LLM inference (llama-3.1-8b-instruct-fp8-fast) | Cloudflare Workers AI | RCA generation, LLM judging |
| Safety filter + embeddings (Llama Guard 3, BGE-Base-EN) | Cloudflare Workers AI | Safety pre-filter, 768-dim embeddings |
| Trace metadata + verdicts | Cloudflare D1 | Structured query access |
| Trace blobs + cassettes | MinIO (S3-compatible, on Azure VM) | Large payload storage — **R2 skipped** (needs credit card) |
| Vector search | xqdrant (`localhost:6333`, internal) | Similar incidents + runbooks — **replaces Vectorize** for search |
| ~~Async eval jobs~~ | — | **Queues skipped** — evaluation runs synchronously |
| Trace + eval UI | Langfuse (self-hosted) | Human-readable trace exploration |
| Atlassian workspace | Jira + Confluence + JSM | Data source + output target |
