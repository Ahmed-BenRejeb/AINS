# Sentinel — AI Agent Reliability Platform for Atlassian

> AINS Hackathon 2026 · Built for [Vectors / covectors.io](https://covectors.io)

Sentinel is a unified reliability platform that continuously evaluates, records, and debugs AI agents running inside the Atlassian ecosystem. Three use cases — one shared system.

---

## What We Built

| Layer | Use Case | What It Does |
|---|---|---|
| **UC2 — Flight Recorder** | `packages/flight-recorder` | Transparently captures every LLM call and tool call during a live agent run, enabling deterministic replay without touching live APIs |
| **UC1 — Eval Engine** | `packages/eval-engine` | Judges agent execution traces using a safety filter + code graders + CF Workers AI LLM-as-judge (with position-bias calibration), produces auditable verdicts with failure attribution and `pass^k` scoring |
| **UC3 — Atlassian Agent** | `packages/atlassian-agent` + `packages/atlassian-remote` | A Rovo AI Agent on Forge that analyzes JSM incidents, finds similar past incidents and runbooks, and drafts root cause analyses — instrumented by UC1 and UC2 |

The three layers share a single [OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/) trace spine. UC2 captures, UC1 judges, UC3 produces the agent runs being captured and judged — and verdicts are filed back as Jira issues.

**Status:** fully built and live-validated. The end-to-end loop runs on the Azure VM — `POST /analyze` records every LLM call into a MinIO cassette, the eval engine judges it and files a Jira Incident on failure, and the response carries the verdict + a replay link. The Forge Rovo Agent (v2.2.0) is deployed and installed on Jira + Confluence at ahmedains.atlassian.net. The dashboard is live at `https://dashboard.ahmedxsaad.me` with all screens including `/reliability` (drift + evaluator quality), mid-replay injection, and bisect. A full K8s/KEDA/Helm deployment stack (`deploy/`) and an embedding interpretability pipeline (`interpretability/`) round out the submission.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-team/sentinel.git
cd sentinel
make setup

# 2. Configure environment
make env          # creates .env from .env.example
# → fill in your values in .env

# 3. Seed Atlassian dev site with synthetic data
make seed

# 4. Embed those incidents + runbooks into xqdrant (required for retrieval)
make seed-xqdrant

# 5. Start development services
make dev

# 6. Run all tests
make test
```

See `Makefile` for all available commands. See `docs/` for the full technical documentation.

---

## Repo Structure

```
sentinel/
│
├── 📦 packages/            All code — one package per bounded concern
│   ├── trace-core/         Shared OTel GenAI schema and types (imported by all packages)
│   ├── flight-recorder/    UC2: record and replay agent execution traces
│   ├── eval-engine/        UC1: evaluate traces, produce verdicts
│   ├── atlassian-agent/    UC3: Forge Rovo Agent + Actions (TypeScript)
│   ├── atlassian-remote/   UC3: heavy compute backend via Forge Remote (Python)
│   └── dashboard/          Shared UI: traces, verdicts, replay, drift, reliability
│
├── 🚀 deploy/              Production deployment manifests
│   ├── k8s/                Kubernetes manifests + KEDA autoscaler + Kustomize
│   ├── helm/sentinel/      Helm chart for the full Sentinel stack
│   ├── docker/             Dockerfiles for each Python service and the dashboard
│   ├── observability/      Prometheus/Grafana stack + ServiceMonitor + Grafana dashboard
│   └── chaos/              ChaosMesh chaos experiments (pod-kill, network-delay, CPU stress)
│
├── 🔬 interpretability/    Embedding interpretability pipeline (5-step: vocab → geometry → attribution)
│
├── 🏗️  infra/              Azure VM + Cloudflare tunnel configuration
│   ├── cloudflare/         Wrangler config for D1, Workers AI, Tunnel
│   └── azure/              VM provisioning scripts and systemd service units
│
├── 📜 scripts/             One-off scripts: data seeding, eval runs, migrations
│
├── 📐 spec/                Protocol gap proposals — our open contribution (bonus points)
│
├── 📚 docs/                Technical documentation, architecture diagram, eval report
│
├── 🧪 tests/               Cross-package end-to-end integration tests
│
├── CLAUDE.md               AI agent instructions (Claude Code reads this automatically)
├── AGENTS.md               AI agent instructions (Codex and other agents)
├── Makefile                Single source of truth for all commands
└── .env.example            Environment variable template
```

Each folder contains a `README.md` explaining what belongs there and why.

---

## Team

| Name | Focus Area |
|---|---|
| — | UC2: Flight Recorder + Infrastructure |
| — | UC1: Eval Engine + Graders |
| — | UC3: Atlassian Agent (Forge) |
| — | UC3: Forge Remote + Dashboard |

---

## Key References
- [Technical Specs Doc](docs/TECHNICAL_SPECS.md)
- [Technical Battle Plan](docs/BATTLE_PLAN.md)
- [Architecture Diagram](docs/ARCHITECTURE.md)
- [Evaluation Report](docs/eval_report.md)
- [Spec Response (Must/Should checklist)](docs/spec_response.md)
- [Validation Guide (demo-day walkthrough)](docs/validation_guide.md)
- [Deployment Guide (K8s/Helm/KEDA)](deploy/README.md)
- [Embedding Interpretability Pipeline](interpretability/README.md)
- [OTel GenAI Replay Extension Spec](spec/otel-genai-replay-extension.md)
- [MCP Audit Trail Proposal](spec/mcp-audit-trail-proposal.md)
