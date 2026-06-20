# dashboard

**The unified human interface for Sentinel.**
A Next.js 16 (App Router, Turbopack) app that shows judges the whole system at a glance:
overview/health, recorded agent runs, per-run execution traces, eval verdicts with
failure attribution, and deterministic replay/bisect. Dark, premium dev-tool feel
(Vercel/Linear), Framer Motion throughout. Pure display layer — produces no data.

Runs on **port 3001**.

## Screens

| Route | Purpose |
|---|---|
| `/` | Overview: stats (Total Runs, Pass Rate, pass^k, Flagged), recent verdicts, flag alert |
| `/runs` | All recorded runs (`GET /runs`) — click a row → trace |
| `/runs/[run_id]` | Execution trace: manifest + staggered step timeline; Replay / View Verdict |
| `/verdicts/[run_id]` | Full verdict: PASS/FAIL/UNCERTAIN hero, per-dimension scores, failure attribution, self-eval, replay link |
| `/replay/[run_id]` | Launch deterministic replay (`POST /replay`) + bisect (`POST /bisect`) |

Plus `app/api/{replay,bisect}/route.ts` — server-side POST proxies (no browser CORS).

## `?mock=true` — the demo safety net

Append `?mock=true` to **any** page to render from realistic fixtures
(`lib/mock-data.ts`) that match the live API shapes exactly. In live mode, if a
service is unreachable the page automatically falls back to mock data — so a screen
never breaks during judging. A `DataSourceBadge` shows whether you're seeing
`LIVE`, `MOCK DATA`, or `MOCK (fallback)`. All fetches are server-side.

> Note: the eval engine currently exposes only `/health` + `POST /evaluate`, so the
> verdict screens run on mock-fallback in live mode until a `GET /verdicts` endpoint
> exists. The UI already tries it and will light up automatically when it does.

## Stack

Next.js 16 App Router · Tailwind CSS · hand-rolled shadcn-style primitives
(`components/ui/*`) · Framer Motion · lucide-react. Fonts use system stacks (no
remote font host), so the build is fully offline-safe. Types in `lib/types.ts`
mirror `trace-core/schema.ts`.

## Setup

```bash
pnpm --filter dashboard install
pnpm --filter dashboard dev        # dev server on :3001
pnpm --filter dashboard build      # production build
pnpm --filter dashboard typecheck  # tsc --noEmit
pnpm --filter dashboard lint
```

Override service URLs per-env with `NEXT_PUBLIC_FLIGHT_RECORDER_URL`,
`NEXT_PUBLIC_EVAL_ENGINE_URL`, `NEXT_PUBLIC_FORGE_REMOTE_URL`,
`NEXT_PUBLIC_LANGFUSE_URL` (defaults are the live production URLs).
