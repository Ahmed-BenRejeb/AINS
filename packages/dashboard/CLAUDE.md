# dashboard / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**The unified Sentinel UI.** A Next.js 16 (App Router, Turbopack) app that gives judges the
human-facing view of the whole system: the overview/health, recorded agent runs,
per-run execution traces, eval verdicts (with failure attribution + self-eval),
and deterministic replay/bisect. Premium dev-tool feel (Vercel/Linear), dark
theme, Framer Motion throughout.

Runs on **port 3001**.

## Stack

- **Next.js 16 App Router** (Turbopack builds; React 18.3 — Next 16 supports `^18.2`).
  Server components fetch; client components animate. `params`/`searchParams` are
  **Promises** (Next 15+), awaited in every page.
- **Tailwind CSS** with a small hand-rolled **shadcn-style** primitive set
  (`components/ui/*`) — built by hand rather than via the shadcn CLI so the build
  needs no network. Uses `class-variance-authority` + `clsx` + `tailwind-merge`.
- **Framer Motion** for all animation (page fade-in, verdict scale-spring + green
  pulse / red shake, staggered step timeline, hover lift, counting stats).
- **lucide-react** icons.
- Fonts use **system stacks** (declared in `app/globals.css`), not
  `next/font/google`, so the production build never depends on a remote font host.

## Key Files

```
dashboard/
├── package.json            scripts: dev/build/start (port 3001), lint, typecheck, format, test (=tsc)
├── tailwind.config.ts      dark palette: canvas #0A0A0A, card #141414, hairline #1F1F1F + verdict accents
├── app/
│   ├── layout.tsx          dark shell + SiteHeader (Suspense-wrapped: it reads searchParams)
│   ├── globals.css         theme tokens, grid texture, scrollbar, font-var stacks
│   ├── loading.tsx         skeleton route-transition state (never spinners)
│   ├── error.tsx           last-resort boundary (offers "open demo / mock")
│   ├── not-found.tsx
│   ├── page.tsx                          (1) overview
│   ├── runs/page.tsx                     (2) all recorded runs
│   ├── runs/[run_id]/page.tsx            (3) execution trace
│   ├── verdicts/[run_id]/page.tsx        (4) verdict detail
│   ├── replay/[run_id]/page.tsx          (5) replay + bisect
│   └── api/{replay,bisect}/route.ts      server-side POST proxies (mock-aware)
├── components/
│   ├── ui/                 card · badge · button · table · skeleton · progress
│   └── sentinel/
│       ├── RunStatusBadge.tsx   PASS/FAIL/UNCERTAIN + run-status colours & icons
│       ├── VerdictCard.tsx      full verdict display (hero + dims + attribution + self-eval)
│       ├── StepTimeline.tsx     staggered vertical execution timeline
│       ├── DimensionTable.tsx   per-dimension rubric scores (right-aligned, inline conf bar)
│       ├── AttributionBox.tsx   failure attribution headline
│       ├── StatsRow.tsx         home metric cards w/ count-up
│       ├── AnimatedCounter / ConfidenceBar / DataSourceBadge / EmptyState / PageHeader / SiteHeader / motion
│       └── views/               *View client components (animation + interactivity) per screen
└── lib/
    ├── api.ts              server-side fetch wrappers, ?mock support, live→mock fallback
    ├── mock-data.ts        realistic fixtures matching the live API shapes exactly
    ├── types.ts            mirrors trace-core/schema.ts + the live API envelopes
    └── utils.ts            cn(), withMock(), truncate/pct/timeAgo helpers
```

## Data Layer — `?mock=true` is the demo safety net

Every accessor in `lib/api.ts` returns `Loaded<T> = { data, source, error? }` where
`source` is `live | mock | mock-fallback`:

- **`?mock=true`** on any page → returns `lib/mock-data.ts` fixtures (`source: mock`).
- **otherwise** → server-fetches the live service; on ANY failure (network, non-2xx,
  timeout, missing endpoint) it falls back to mock and tags `source: mock-fallback`.

So **all 5 screens render in both modes** and never show a broken state. The header
`DataSourceBadge` (and the per-page one) tells the viewer which they're looking at.
Fetches run **server-side** (server components + route handlers), so calling the
live APIs is server-to-server: no browser CORS, no secrets in the client.

`SiteHeader` threads `?mock=true` through every internal link and exposes a toggle,
so demo mode survives navigation.

## Service URLs / Env

Defaults are the live production URLs; override per-env with `NEXT_PUBLIC_*`:

| Env var | Default |
|---|---|
| `NEXT_PUBLIC_FLIGHT_RECORDER_URL` | `https://flight.ahmedxsaad.me` |
| `NEXT_PUBLIC_EVAL_ENGINE_URL` | `https://eval.ahmedxsaad.me` |
| `NEXT_PUBLIC_FORGE_REMOTE_URL` | `https://remote.ahmedxsaad.me` |
| `NEXT_PUBLIC_LANGFUSE_URL` | `https://langfuse.ahmedxsaad.me` |

(These are read in TS, not Python, so `check_docs.py`'s `.env.example` parity check
— which only scans `.py` — does not require them.)

## Known Gotchas

- **The eval engine has no `GET /verdicts` or `GET /verdicts/{id}` endpoint** (only
  `/health` + `POST /evaluate`/`/evaluate/batch`). The UI optimistically tries those
  GETs so it lights up automatically if they're ever added, but until then the
  home "Recent verdicts" table and the verdict detail page run on **mock-fallback**
  in live mode. This is expected — verdicts are produced inside the Phase-4 loop,
  not served from a list endpoint yet.
- **`GET /runs/{id}` trace rows don't carry latency.** The `trace_records` D1 row
  has `input_preview`/`output_preview` but `metadata_json` only stores the hmac
  algorithm — so `StepTimeline` shows `latency_ms` only when present (mock data has
  it; live data degrades gracefully).
- **No `next lint` in Next 16** — it was removed. Lint runs ESLint directly
  (`"lint": "eslint ."`) against an ESLint-9 **flat config** (`eslint.config.mjs`)
  that imports `eslint-config-next`'s native flat array directly. (FlatCompat +
  `next/core-web-vitals` throws "Converting circular structure to JSON" with the v16
  plugins — use the native flat export, not the legacy `extends` path.)
- **pnpm build approval:** a supply-chain policy hook adds `allowBuilds:` to the
  root `pnpm-workspace.yaml`. Both `unrs-resolver` (optional eslint import-resolver
  binary; JS fallback works) and `sharp` (Next 16's `next/image` optimizer — unused
  here) are set to `false`. Without an explicit decision, `pnpm <script>`'s pre-run
  check fails with `ERR_PNPM_IGNORED_BUILDS`.

## Commands

```bash
pnpm --filter dashboard dev          # dev server on :3001
pnpm --filter dashboard build        # production build (zero errors)
pnpm --filter dashboard typecheck    # tsc --noEmit (zero errors)
pnpm --filter dashboard lint         # eslint . (flat config, clean)
# Demo any screen offline: append ?mock=true, e.g. /verdicts/<run_id>?mock=true
```
