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
               │   packages/dashboard  (Next.js)                │
               │                                               │
               │   /traces     → execution graphs              │
               │   /verdicts   → verdict detail + attribution  │
               │   /replay     → step-by-step diff + inject    │
               │   /incidents  → JSM incident + RCA status     │
               └───────────────────────────────────────────────┘
```

---

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
5. atlassian-remote calls Claude (Anthropic API)
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
   Trace (gen_ai.* spans) → Langfuse + D1/R2
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
| `trace-core` | Python + TS | Imported (not deployed) | `uv add sentinel-trace-core` / npm |
| `flight-recorder` | Python | Azure VM | systemd service, port 8001 |
| `eval-engine` | Python | Azure VM | systemd service, port 8000 |
| `atlassian-agent` | TypeScript | Atlassian (Forge) | `forge deploy` |
| `atlassian-remote` | Python | Azure VM | systemd service, port 8080 |
| `dashboard` | TypeScript | Cloudflare Pages / Azure VM | `pnpm build` + static serve |

All Azure VM services are exposed externally via **Cloudflare Tunnel** only. The VM has no open ports except SSH (22).

---

## External Services

| Service | Provider | Used For |
|---|---|---|
| LLM inference (Claude claude-sonnet-4-6) | Anthropic API | RCA generation, LLM judging |
| LLM inference (Llama Guard 3, BGE-Base-EN) | Cloudflare Workers AI | Safety filter, embeddings |
| Trace metadata + verdicts | Cloudflare D1 | Structured query access |
| Trace blobs + cassettes | Cloudflare R2 | Large payload storage |
| Vector search | Cloudflare Vectorize | Similar incidents + runbooks |
| Async eval jobs | Cloudflare Queues | Decouple eval from agent run |
| Trace + eval UI | Langfuse (self-hosted) | Human-readable trace exploration |
| Atlassian workspace | Jira + Confluence + JSM | Data source + output target |
