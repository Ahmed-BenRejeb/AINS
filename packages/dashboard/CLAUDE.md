# dashboard / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**The shared UI.** A Next.js app that provides the human-facing view of the entire Sentinel system: execution traces, eval verdicts, replay timelines, incident status, and drift charts. This is what judges see during the demo.

## Key Files

```
dashboard/
├── package.json
├── tsconfig.json       ← strict TypeScript
├── next.config.ts
├── app/
│   ├── layout.tsx
│   ├── page.tsx             ← overview: recent runs, pass^k chart, active alerts
│   ├── traces/
│   │   ├── page.tsx         ← trace list (all recorded runs)
│   │   └── [run_id]/
│   │       └── page.tsx     ← execution graph for one run
│   ├── verdicts/
│   │   ├── page.tsx         ← verdict list with filter/sort
│   │   └── [run_id]/
│   │       └── page.tsx     ← full verdict detail: dimensions, attribution, self-eval
│   ├── replay/
│   │   └── [run_id]/
│   │       └── page.tsx     ← replay timeline: step-by-step, diff view, inject mode
│   └── incidents/
│       └── page.tsx         ← recent JSM incidents + their RCA status
├── components/
│   ├── ExecutionGraph.tsx   ← step-by-step visualization of a trace (key demo component)
│   ├── VerdictCard.tsx      ← displays a verdict with dimensions + attribution
│   ├── ReplayTimeline.tsx   ← replay mode UI with inject editor
│   ├── DriftChart.tsx       ← drift detection chart over time
│   └── PassAtKChart.tsx     ← pass^k reliability chart
└── lib/
    ├── api.ts               ← typed fetch wrappers for the eval-engine and flight-recorder APIs
    └── types.ts             ← re-exports from trace-core (no duplication)
```

## Design Priorities

This is a **demo tool for judges**, not a production product. Prioritize in this order:
1. **Working** — the data shows up correctly
2. **Clear** — a non-AI engineer can understand what they're looking at
3. **Polished** — looks professional (use shadcn/ui components)

Do **not** spend time on:
- Authentication/login (not needed for demo)
- Pagination (demo dataset is small)
- Mobile responsiveness
- Dark mode

## Key Demo Screens (Build These First)

### 1. Run Detail (Execution Graph)
The most important screen for the demo. Shows a run as a timeline of steps:
- Each step shows: kind (llm_call / tool_call), timestamp, latency, pass/fail
- Click a step → expand to see full input/output
- "Replay this run" button → links to replay view
- "View verdict" button → links to verdict detail

### 2. Verdict Detail
Shows a verdict in human-readable form:
- Overall verdict badge (pass / fail / uncertain)
- Per-dimension scores (correctness, efficiency, safety, reasoning)
- Failure attribution: "Step 2 (retrieval) — confidence 87%"
- Self-evaluation: confidence score + critique text + "flagged for human review" badge
- Replay link + recommended action

### 3. Replay Timeline
Shows the replay diff:
- Side-by-side: original step vs. replayed step
- Highlight divergence points in red
- Inject editor: text area to modify a step's output → "Fork from here" button

## Component Patterns

```tsx
// ✅ Use shadcn/ui for all UI components — consistent, professional
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

// ✅ Data fetching: use React Server Components + fetch (Next.js App Router)
// in app/verdicts/[run_id]/page.tsx:
export default async function VerdictPage({ params }: { params: { run_id: string } }) {
  const verdict = await getVerdict(params.run_id);  // lib/api.ts
  return <VerdictCard verdict={verdict} />;
}

// ✅ API types come from lib/types.ts which re-exports from trace-core
import type { EvalVerdict, TraceRecord } from "@/lib/types";
```

## Commands

```bash
cd packages/dashboard && pnpm dev          # start dev server on port 3001
cd packages/dashboard && pnpm build        # production build
cd packages/dashboard && pnpm test         # run vitest
cd packages/dashboard && pnpm typecheck    # tsc --noEmit
cd packages/dashboard && pnpm lint         # eslint
```

## Known Gotchas

- **The eval-engine API runs on port 8000, the dashboard on 3001.** Set `NEXT_PUBLIC_EVAL_API_URL=http://localhost:8000` in your `.env.local` for local dev.
- **ExecutionGraph can have 20+ nodes for a complex run.** Use a virtual list or pagination if the graph becomes slow. But for the hackathon demo, keep agent runs under 15 steps so this isn't an issue.
- **Replay inject mode modifies state on the flight-recorder side.** The dashboard just sends the modification; the replay engine applies it. This is intentional — the dashboard is display-only.
