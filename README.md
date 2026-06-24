<div align="center">

# 🛰️ Sentinel

### The reliability layer for enterprise AI agents.

**Record every run · Replay it deterministically · Evaluate the trajectory · File an auditable verdict back into Jira — continuously.**

`AINS Hackathon 2026` · in partnership with [Vectors](https://covectors.io) · *AI for Enterprise Automation*

![status](https://img.shields.io/badge/status-final%20%E2%80%94%20complete-2ea44f?style=flat-square)
![tests](https://img.shields.io/badge/tests-167%20Python%20%2B%2025%20TS%20green-2ea44f?style=flat-square)
![typecheck](https://img.shields.io/badge/mypy%20--strict%20%C2%B7%20ruff-clean-2ea44f?style=flat-square)
![deployed](https://img.shields.io/badge/Forge%20%C2%B7%20VM%20%C2%B7%20dashboard-live-2ea44f?style=flat-square)
![python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![next](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=nextdotjs&logoColor=white)

[Architecture](docs/ARCHITECTURE.md) · [Eval Report](docs/eval_report.md) · [Scalability & Reliability](docs/scalability_reliability.md) · [How It Works](docs/how_it_works.md) · [Open-Contribution Specs](spec/)

</div>

---

<div align="center">

<img src="docs/screenshots/dashboard-overview.png" alt="Sentinel dashboard overview: the flight recorder for AI agents, with live pass-rate ring and recent verdicts" width="92%">

<sub>**The dashboard** — flight-recorder home with live pass-rate telemetry and recent verdicts · `dashboard.ahmedxsaad.me`</sub>

</div>

---

## The problem

Enterprises are shipping AI agents that **fail silently**. The same instruction, given twice, produces different tool calls and different outputs — so traditional unit tests, which match exact output, are structurally incompatible. An agent can look busy, reason intelligently, call the right‑*looking* tools, and still corrupt a Jira ticket, overwrite a Confluence page, or mis‑route a JSM workflow. **The failure only becomes visible after the side effect — when the damage is already done.**

There is no infrastructure today that captures the full execution trajectory of an agent run, evaluates it, attributes failure to a specific component, and does it *continuously* on every production run.

## The solution — one platform, three jobs, one loop

Sentinel is that infrastructure. It unifies **all three hackathon use cases into a single self‑reinforcing system** — and we dogfooded it on a real Rovo agent we deployed to Atlassian.

```
        ┌──────────────────────────────────────────────────────────────┐
        │                                                              │
        ▼                                                              │
  ┌───────────┐     ┌────────────────┐     ┌─────────────┐     ┌──────────────┐
  │   UC3     │     │     UC2        │     │    UC1      │     │   Verdict    │
  │ Rovo Agent│ ──► │ Flight Recorder│ ──► │ Eval Engine │ ──► │ → Jira issue │
  │ (Forge)   │     │ record + replay│     │ judge + RCA │     │ + Dashboard  │
  └───────────┘     └────────────────┘     └─────────────┘     └──────────────┘
   acts in Jira      taped, hash-chained     failure attribution,   the loop
   & Confluence      deterministic replay    pass^k, drift, κ       closes
```

> **Remove the AI and the system ceases to exist.** Its entire job is evaluating, replaying, and reasoning over *non‑deterministic* AI. There is no degraded non‑AI version — the intelligence is the mechanism.

| | Use Case | Package | What it does |
|---|---|---|---|
| **UC2** | Agent Execution Tracer & **Deterministic Replay** | [`flight-recorder`](packages/flight-recorder) | Transparently intercepts every LLM + tool call (httpx transport override), tapes it into a cassette with a **hash‑chained HMAC audit trail**, and replays it **with 0 live API calls** — plus mid‑replay divergence injection. |
| **UC1** | **Continuous Evaluation** of non‑deterministic agents | [`eval-engine`](packages/eval-engine) | Multi‑level grading (deterministic code grader + Llama‑Guard safety + calibrated LLM‑as‑judge), **DAG failure attribution to the exact step**, `pass^k` reliability, **drift detection**, and **evaluator‑of‑evaluator** (Cohen's κ). Files a Jira Incident on a flagged verdict. |
| **UC3** | AI Automation for the **Atlassian Workspace** | [`atlassian-agent`](packages/atlassian-agent) + [`atlassian-remote`](packages/atlassian-remote) | A real **Rovo Agent on Forge** (installed on Jira **and** Confluence): incident RCA + **semantic duplicate resolver** over vector search. Structured output into Jira, never chat. Low confidence → **flags a human, never auto‑acts**. |

The three layers share one [OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/) trace spine: **UC3 produces the runs, UC2 records them, UC1 judges them, and the verdict lands back in Jira.**

---

## Proof it works (measured, not claimed)

| Dimension | Evidence |
|---|---|
| **Reliability metric** | `pass@1` **100%** / `pass^8` **33.3%** — the τ‑bench‑style consistency gap that pass@1 alone hides ([eval report](docs/eval_report.md)) |
| **Evaluator quality** | **Cohen's κ** (chance‑corrected judge‑vs‑human agreement) — so a constant "pass" judge scores ~0, not a flattering accuracy |
| **Deterministic replay** | Replays a full run with **0 live LLM calls** — guarantees reproducible debugging *and* a deterministic demo |
| **Scales horizontally** | **KEDA** autoscales the eval engine **1 → 5** on CPU; **k6 load test: 153,833 requests, 1,282 req/s, p95 190 ms, 0% errors @ 200 concurrent users** ([details](docs/scalability_reliability.md)) |
| **Survives chaos** | 5 pods killed mid‑traffic → **100% availability, zero downtime**, automatic self‑healing |
| **Engineering rigour** | **167 Python tests** green; `mypy --strict` + `ruff` clean; Helm lint clean |

<div align="center">

<img src="docs/screenshots/reliability-drift-evaluator.png" alt="Sentinel reliability screen: behavioural drift panel and evaluator-quality panel showing Cohen's kappa and per-label human agreement" width="92%">

<sub>**Reliability over time** — behavioural drift across run windows, and judge-vs-human agreement as chance-corrected **Cohen's κ** (not flattering raw accuracy).</sub>

</div>

---

## Live system

The full stack runs on an Azure VM behind a Cloudflare Tunnel; the Forge app is deployed to a live Atlassian site.

| Service | URL |
|---|---|
| Dashboard (traces · verdicts · replay) | `https://dashboard.ahmedxsaad.me` |
| Eval Engine API (UC1) | `https://eval.ahmedxsaad.me` |
| Flight Recorder API (UC2) | `https://flight.ahmedxsaad.me` |
| Forge Remote backend (UC3) | `https://remote.ahmedxsaad.me` |
| Langfuse (LLM trace UI) | `https://langfuse.ahmedxsaad.me` |
| Rovo Agent | installed on Jira **+** Confluence at `ahmedains.atlassian.net` |

> Public hostnames sit behind Cloudflare's bot challenge — browsers pass, `curl` gets a `403` (expected, not an outage).

<div align="center">

<img src="docs/screenshots/jira-filed-incidents.png" alt="Jira AO project board showing Sentinel eval verdicts filed as auditable incidents, reported by the agent" width="92%">

<sub>**The loop closes in Jira** — every evaluated run is filed back as an auditable AO incident with its verdict, so reliability lives where the team already works.</sub>

</div>

---

## Architecture

```
ATLASSIAN CLOUD                          AZURE VM (Cloudflare Tunnel)              CLOUDFLARE
┌────────────────────┐   Forge Remote   ┌──────────────────────────────┐         ┌────────────────┐
│ atlassian-agent    │ ───────────────► │ atlassian-remote  (FastAPI)  │ ──────► │ Workers AI     │
│ Rovo Agent + 7     │      HTTPS       │ /analyze /duplicates /search │  embed  │ Llama 3.1 8B   │
│ Forge Actions (TS) │ ◄─────────────── │   │ records via UC2          │  +RCA   │ Llama Guard 3  │
└────────────────────┘   verdict/issue  │   ▼                          │  +judge │ BGE embeddings │
                                        │ flight-recorder (UC2)        │         └────────────────┘
                                        │   tape → MinIO cassette      │         ┌────────────────┐
                                        │   hash-chain audit → D1      │ ──────► │ D1 (traces)    │
                                        │   ▼                          │         │ Vectorize      │
                                        │ eval-engine (UC1)            │         └────────────────┘
                                        │   judge → verdict → Jira     │   xqdrant (vector search)
                                        │ dashboard (Next.js)          │   MinIO (cassettes)
                                        └──────────────────────────────┘   Langfuse (LLM traces)
```

Full diagram + data flow: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

**Stack:** Cloudflare Workers AI (Llama 3.1‑8B judge, Llama Guard, BGE‑768) · Forge TS SDK · FastAPI · Next.js 16 · xqdrant (Qdrant fork) · MinIO · Cloudflare D1 · Kubernetes + KEDA + Prometheus/Grafana · Langfuse.

---

## Mermaid diagrams

> Paste any block into [mermaid.live](https://mermaid.live) to render it. Per-package internals: [trace-core](packages/trace-core/DIAGRAM.md) · [flight-recorder](packages/flight-recorder/DIAGRAM.md) · [eval-engine](packages/eval-engine/DIAGRAM.md) · [atlassian-remote](packages/atlassian-remote/DIAGRAM.md) · [atlassian-agent](packages/atlassian-agent/DIAGRAM.md) · [dashboard](packages/dashboard/DIAGRAM.md) · [deploy](deploy/DIAGRAM.md)

### 1. High-level system (the three use cases as one loop)

```mermaid
flowchart TB
    subgraph ATL["Atlassian Cloud (ahmedains.atlassian.net)"]
        JSM["Jira / JSM / Confluence"]
        AGENT["atlassian-agent (Forge, TypeScript)<br/>Rovo agent 'Sentinel Incident Responder'<br/>7 actions"]
        JSM <--> AGENT
    end

    subgraph VM["Azure VM (services behind Cloudflare Tunnel)"]
        REMOTE["atlassian-remote :8080<br/>/analyze /duplicates /search /embed"]
        FLIGHT["flight-recorder :8001<br/>/runs /replay /bisect"]
        EVAL["eval-engine :8000<br/>/evaluate /drift /evaluator-quality /verdicts"]
        DASH["dashboard :3001 (Next.js)"]
        LF["Langfuse :3000"]
        XQ["xqdrant :6333 (internal)"]
        MINIO["MinIO :9090 (internal)"]
    end

    subgraph CF["Cloudflare"]
        AI["Workers AI<br/>llama-3.1-8b-instruct-fp8-fast (chat)<br/>bge-base-en-v1.5 (embed)<br/>llama-guard-3-8b (safety)"]
        D1["D1: run_manifests, trace_records, eval_verdicts"]
    end

    AGENT -->|"callRemote: X-Sentinel-Secret + X-Account-Id"| REMOTE
    REMOTE -->|cf_ai_embed / cf_ai_chat| AI
    REMOTE -->|search_similar query_points| XQ
    REMOTE -->|"RunRecorder taping (UC2)"| FLIGHT
    REMOTE -->|"request_evaluation POST /evaluate"| EVAL

    FLIGHT -->|cassette blobs| MINIO
    FLIGHT -->|"audit chain + manifest"| D1
    EVAL -->|"safety + calibrated judge"| AI
    EVAL -->|load_cassette_records| MINIO
    EVAL -->|persist_verdict| D1
    EVAL -->|"_file_issue on fail/flag"| JSM

    REMOTE -.langfuse.-> LF
    EVAL -.langfuse.-> LF
    FLIGHT -.langfuse.-> LF

    DASH -->|"/runs /replay /bisect"| FLIGHT
    DASH -->|"/verdicts /drift /evaluator-quality"| EVAL
    DASH -.deep links.-> LF
```

### 2. Package dependency graph (enforced, no cycles)

```mermaid
flowchart TD
    TC["trace-core<br/>types + constants + hash_utils + otel"]
    FR["flight-recorder (UC2)"]
    EE["eval-engine (UC1)"]
    AR["atlassian-remote (UC3 backend)"]
    AA["atlassian-agent (UC3 Forge, TS)"]
    DB["dashboard (Next.js)"]
    MINIO[("MinIO cassette")]

    TC --> FR
    TC --> EE
    TC --> AR
    FR -->|"AsyncRecordingTransport + write_run_manifest"| AR
    EE -.->|"reads cassette over S3, not an import"| MINIO
    AA -.->|"HTTP only (callRemote)"| AR
    DB -.->|"types mirror schema.ts + HTTP"| FR
    DB -.-> EE

    classDef shared fill:#0f3,stroke:#0a0,color:#000;
    class TC shared;
```

### 3. End-to-end data flow: `POST /analyze` → recorded + judged verdict

```mermaid
sequenceDiagram
    autonumber
    participant AG as atlassian-agent
    participant API as atlassian-remote api.py
    participant AN as analyzer.analyze_incident
    participant JIRA as AtlassianClient
    participant REC as RunRecorder (UC2)
    participant CF as cf_ai_client
    participant XQ as vector_search / xqdrant
    participant RCA as rca_generator
    participant EC as eval_client
    participant EE as eval-engine

    AG->>API: POST /analyze {incident_key, requested_by}
    API->>API: verify_request (X-Sentinel-Secret)
    API->>AN: analyze_incident()
    AN->>JIRA: get_issue → extract_incident_text (flatten ADF)
    AN->>REC: run_id = new_run_id(), then with RunRecorder(run_id)
    Note over REC,CF: using_transport binds AsyncRecordingTransport via contextvar
    AN->>CF: cf_ai_embed_query(incident_text)  [taped step]
    AN->>XQ: search_similar(incidents, embedding)  [tool_call record_event]
    AN->>XQ: search_similar(runbooks, embedding)  [tool_call record_event]
    AN->>RCA: generate_rca → cf_ai_chat → RcaDraft  [taped step]
    AN->>REC: persist_manifest (run_manifests D1 row)
    AN->>EC: request_evaluation(run_id)
    EC->>EE: POST /evaluate {run_id}
    EE-->>EC: EvalVerdict (or files AO Incident on fail/flag)
    EC-->>AN: eval_verdict (best-effort, may be None)
    AN-->>AG: AnalyzeResult{run_id, rca_draft, similar, runbooks,<br/>flag_for_human, eval_verdict, replay_link}
```

### 4. Deployment topology

```mermaid
flowchart LR
    subgraph Forge["Atlassian Forge (nodejs22.x)"]
        AA["atlassian-agent<br/>forge deploy -e development"]
    end
    subgraph Tunnel["Cloudflare Tunnel 'sentinel'"]
        I1["remote.ahmedxsaad.me"]
        I2["eval.ahmedxsaad.me"]
        I3["flight.ahmedxsaad.me"]
        I4["dashboard.ahmedxsaad.me"]
        I5["langfuse.ahmedxsaad.me"]
    end
    subgraph AzureVM["Azure VM 48.220.48.34 (only SSH:22 open)"]
        S1["sentinel-remote.service :8080"]
        S2["sentinel-eval.service :8000"]
        S3["sentinel-flight.service :8001"]
        S4["sentinel-dashboard.service :3001"]
        DK["Docker: Langfuse :3000 + MinIO :9090 + xqdrant :6333"]
    end

    AA --> I1
    I1 --> S1
    I2 --> S2
    I3 --> S3
    I4 --> S4
    I5 --> DK
```

---

## Quick start

```bash
git clone https://github.com/ahmedxsaad/AINS.git && cd AINS
make setup          # install all deps (Python uv workspace + Node)
make env            # create .env from .env.example, then fill it in
make seed           # seed the Atlassian dev site with synthetic incidents + runbooks
make seed-xqdrant   # embed them into xqdrant (required for retrieval)
make dev            # start the services locally
make test           # run all tests (167 Python + TS jest)
make check          # lint + typecheck + docs parity (run before every commit)
```

### Deploy on Kubernetes (scalability + observability + chaos)

```bash
# Minikube + KEDA autoscaling, Prometheus/Grafana, chaos experiments — all under deploy/
kubectl apply -k deploy/k8s                                   # the stack in its own `sentinel` namespace
kubectl apply -f deploy/k8s/keda/                             # KEDA ScaledObject (1→5 on CPU)
kubectl apply -f deploy/k8s/load/k6/k6-job.yaml               # measured load test
bash deploy/chaos/pod-kill.sh && bash deploy/chaos/steady-state.sh   # prove self-healing
```

See **[deploy/README.md](deploy/README.md)**, **[deploy/observability/](deploy/observability/)**, and **[deploy/chaos/](deploy/chaos/)**.

---

## Repo structure

```
AINS/
├── packages/
│   ├── trace-core/        Shared OTel GenAI schema + types (the contract all packages import)
│   ├── flight-recorder/   UC2 · record / replay / bisect / divergence-inject (Python)
│   ├── eval-engine/       UC1 · graders, calibrated judge, attribution, pass^k, drift, κ (Python)
│   ├── atlassian-agent/   UC3 · Forge Rovo Agent + 7 actions (TypeScript)
│   ├── atlassian-remote/  UC3 · heavy-compute backend: embeddings, vector search, RCA (Python)
│   └── dashboard/         Unified UI · traces, verdicts, replay, divergence editing (Next.js)
├── deploy/                Kubernetes + KEDA + Helm + observability + chaos
├── interpretability/      Offline embedding interpretability pipeline (vocab → geometry → attribution)
├── infra/                 Cloudflare (D1/Vectorize/Tunnel) + Azure VM provisioning
├── scripts/               Data seeding + synthetic eval runs
├── spec/                  Protocol-gap proposals — our open contribution (bonus)
├── docs/                  Architecture, eval report, scalability/reliability, how-it-works
└── tests/                 Cross-package end-to-end integration tests
```

---

## How we score against the brief

- **AI is the mechanism, not a feature** — remove the LLM judge / embeddings / RCA and there is no evaluation, no semantic dedup, no attribution. Chained prompts + structured extraction + DAG attribution, *not* input→LLM→paste.
- **Explainability & auditability** — every verdict says *what the agent should have done, what it did, where it diverged, and the recommended action*, with confidence, retrieval evidence, and a tamper‑evident audit chain.
- **Evaluation & rigour** — a real protocol on a synthetic test set; non‑determinism handled via position‑bias calibration, `pass^k`, and Cohen's κ.
- **Bonus points claimed** — **protocol gap documented** ([OTel GenAI replay extension](spec/otel-genai-replay-extension.md), [MCP audit‑trail proposal](spec/mcp-audit-trail-proposal.md)) · **self‑evaluation** (confidence + flag‑for‑human) · **open contribution** (the spec/ artifacts).

---

## Team

Team **Selecao** — AINS Hackathon 2026

| Member | Focus |
|---|---|
| **Ahmed Saad** ([@ahmedxsaad](https://github.com/ahmedxsaad)) | UC2 Flight Recorder · integration loop · dashboard · infra |
| **Ahmed Ben Rejeb** | UC1 drift + evaluator‑quality · UC3 semantic duplicate resolver · K8s/KEDA scalability |
| **Moetez Fradi** | UC3 Forge Rovo Agent · Atlassian integration |

---

## Key references

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System components, data flow, AI pipeline |
| [docs/how_it_works.md](docs/how_it_works.md) | The end‑to‑end loop, explained |
| [docs/eval_report.md](docs/eval_report.md) | Metrics, protocol, results (`pass^k`, κ, drift) |
| [docs/scalability_reliability.md](docs/scalability_reliability.md) | KEDA / k6 / chaos numbers + design facts |
| [docs/spec_response.md](docs/spec_response.md) | Point‑by‑point answer to every acceptance criterion |
| [docs/TECHNICAL_SPECS.md](docs/TECHNICAL_SPECS.md) · [docs/BATTLE_PLAN.md](docs/BATTLE_PLAN.md) | Full technical spec + build plan |
| [spec/](spec/) | Open‑contribution protocol proposals |
