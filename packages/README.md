# packages/

This directory contains all application code, split into six packages.

---

## Why a Monorepo with Multiple Packages?

A single flat `src/` folder would make it impossible to clearly own, test, or deploy individual concerns. The split here follows a specific principle:

> **Each package has exactly one reason to exist, one team member who owns it, one language, and one deployment target.**

If you find yourself unsure which package a new file belongs to, the answer is almost certainly that the boundary between two packages needs to be sharpened — not that you need a new package.

---

## The Six Packages

```
packages/
├── trace-core/           The shared contract — types and schemas only
├── flight-recorder/      UC2 — capture and replay
├── eval-engine/          UC1 — judge and score
├── atlassian-agent/      UC3 — Atlassian-native (Forge, TypeScript)
├── atlassian-remote/     UC3 — heavy compute (Python, Azure VM)
└── dashboard/            The human-facing UI across all three UCs
```

---

## Package Boundaries Explained

### `trace-core` — The Shared Contract

**What it is:** The single source of truth for all data types — OTel GenAI trace schemas, verdict schemas, audit record schemas, and shared constants.

**Why it's separate:** Every other package imports from here. If types lived inside `flight-recorder` or `eval-engine`, other packages would have circular imports or duplicate definitions. `trace-core` has zero dependencies on any other local package.

**Rule:** If a type is used by more than one package, it lives here. If a type is only used inside one package, it stays there.

**Language:** Python (+ auto-generated TypeScript types for the dashboard)

---

### `flight-recorder` — Capture and Replay (UC2)

**What it is:** A transparent interception layer that sits between an AI agent and its external calls (LLM APIs, MCP tools). Records everything. Replays deterministically.

**Why it's separate:** This package is pure infrastructure — no Atlassian knowledge, no eval logic, no UI. It answers one question: *"what did the agent do, and can we re-run it identically?"* Keeping it separate means it can be tested in complete isolation and reused by any agent, not just UC3.

**Language:** Python · **Deployed on:** Azure VM

---

### `eval-engine` — Judge and Score (UC1)

**What it is:** A multi-level evaluation pipeline that consumes traces from `flight-recorder` and produces structured verdicts: what passed, what failed, which step caused it, how confident the judge is.

**Why it's separate:** Evaluation logic is completely independent from capture logic. The eval engine doesn't care how a trace was recorded — only what it contains. This means you can swap the recording mechanism without touching the evaluation logic, and vice versa.

**Language:** Python · **Deployed on:** Azure VM

---

### `atlassian-agent` — Atlassian-Native Layer (UC3)

**What it is:** The Forge app. Defines the Rovo Agent manifest and its Actions. Handles everything that must run inside Atlassian's infrastructure: fetching Jira/JSM/Confluence data, posting comments, creating pages.

**Why it's separate:** Forge apps are TypeScript-only and run inside Atlassian's sandboxed serverless environment with strict compute limits. This code cannot run anywhere else, and cannot be mixed with the Python backend.

**Language:** TypeScript · **Deployed on:** Atlassian infrastructure (via `forge deploy`)

---

### `atlassian-remote` — Heavy Compute Backend (UC3)

**What it is:** The Python backend that `atlassian-agent` calls via Forge Remote. Does everything the Forge sandbox cannot: text embedding, vector search, large LLM calls for RCA generation.

**Why it's separate from `atlassian-agent`:** Forge's sandbox has a 25-second timeout and limited memory. Heavy compute must run externally. It's also separate from `eval-engine` because its job is *generation* (drafting an RCA), not *evaluation* (judging a trace).

**Language:** Python · **Deployed on:** Azure VM

---

### `dashboard` — The Human Interface

**What it is:** A Next.js web app providing a unified view: execution graphs, verdict details, replay timelines, drift charts, incident status.

**Why it's separate:** The dashboard consumes data from multiple packages but produces none. It has no business logic. Keeping it separate means frontend and backend work don't block each other.

**Language:** TypeScript (Next.js) · **Deployed on:** Cloudflare Pages or Azure VM

---

## Dependency Rules (DAG — no cycles allowed)

```
trace-core       ← imported by everyone, imports nothing local
flight-recorder  ← imports trace-core only
eval-engine      ← imports trace-core only (reads cassettes from MinIO over S3, not the package)
atlassian-remote ← imports trace-core + flight-recorder (records its RCA runs via UC2)
atlassian-agent  ← imports nothing local (calls atlassian-remote via HTTP)
dashboard        ← imports trace-core types only (via generated TS types)
```

`atlassian-remote → flight-recorder` is the one allowed cross-UC package edge: the
Phase 4 loop *records* every RCA run with UC2's `AsyncRecordingTransport` +
`write_run_manifest`, so reusing the recorder library (behaviour, not just types) is
correct. The rule that still holds: never duplicate a **type** — if a schema is shared,
it goes in `trace-core` (e.g. `eval-engine` reads the cassette blob over S3 rather than
importing `flight-recorder` to learn its shape).

---

Each package contains:
- `README.md` — for humans: what it does, setup, how to run
- `CLAUDE.md` — for AI agents: patterns, gotchas, what NOT to do
