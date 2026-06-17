# dashboard

**The human interface for all of Sentinel.**
A Next.js app providing a unified view: execution graphs, verdict details, replay timelines, drift charts, and incident status. This is what judges see during the demo.

---

## What Goes Here

- Next.js App Router pages for each major view (traces, verdicts, replay, incidents)
- React components: ExecutionGraph, VerdictCard, ReplayTimeline, DriftChart, PassAtKChart
- Typed API clients for `eval-engine` (port 8000) and `flight-recorder` (port 8001)
- TypeScript type imports from `trace-core` (re-exported, never redefined)

## What Does NOT Go Here

- Business logic, data processing, or AI calls
- Database queries or direct Cloudflare API calls
- Any Python code

## Why It Exists

The dashboard consumes data from multiple packages but produces none. It is a pure display layer. Keeping it separate means one teammate can own it completely without blocking backend work, and backend changes don't require touching frontend code.

## Design Priority for the Hackathon

**Working > Clear > Polished.** In that order. Use `shadcn/ui` components throughout for a professional look with minimal custom CSS. Do not spend time on authentication, pagination, or mobile responsiveness — these are irrelevant for the demo.

## Key Demo Screens (Build These First)

1. **Run Detail (Execution Graph)** — the most important demo screen. Shows a run as a step-by-step timeline. Click a step to see full input/output. "Replay" and "View verdict" buttons.
2. **Verdict Detail** — per-dimension scores, failure attribution ("Step 2, retrieval, confidence 87%"), self-evaluation badge, replay link, recommended action.
3. **Replay Timeline** — side-by-side diff of original vs. replayed steps, highlighted divergences, inject editor.

## Structure

```
dashboard/
├── app/
│   ├── page.tsx                 overview: recent runs, pass^k chart, alerts
│   ├── traces/[run_id]/page.tsx execution graph
│   ├── verdicts/[run_id]/page.tsx verdict detail
│   ├── replay/[run_id]/page.tsx  replay timeline + inject editor
│   └── incidents/page.tsx        JSM incident list + RCA status
├── components/
│   ├── ExecutionGraph.tsx
│   ├── VerdictCard.tsx
│   ├── ReplayTimeline.tsx
│   ├── DriftChart.tsx
│   └── PassAtKChart.tsx
└── lib/
    ├── api.ts                   typed fetch wrappers
    └── types.ts                 re-exports from trace-core (no duplication)
```

## Setup

```bash
cd packages/dashboard
pnpm install
pnpm dev          # dev server on port 3001
pnpm build
pnpm test
pnpm typecheck
```

Set `NEXT_PUBLIC_EVAL_API_URL=http://localhost:8000` in `packages/dashboard/.env.local` for local dev.
