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

# 4. Start development services
make dev

# 5. Run all tests
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
│   └── dashboard/          Shared UI: traces, verdicts, replay, incidents
│
├── 🏗️  infra/              Infrastructure configuration (not application code)
│   ├── cloudflare/         Wrangler config for D1, Vectorize, Workers AI, Tunnel
│   └── azure/              Azure VM provisioning scripts and systemd services
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
- [Techincal specs Doc](docs/TECHNICAL_SPECS.md)
- [Technical Battle Plan](docs/BATTLE_PLAN.md)
- [Architecture Diagram](docs/ARCHITECTURE.md)
- [Evaluation Report](docs/eval_report.md)
- [OTel GenAI Replay Extension Spec](spec/otel-genai-replay-extension.md)
- [MCP Audit Trail Proposal](spec/mcp-audit-trail-proposal.md)
