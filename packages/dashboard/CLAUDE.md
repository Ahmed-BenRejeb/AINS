# dashboard / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**The unified Sentinel UI.** A Next.js 16 (App Router, Turbopack) app that gives judges the
human-facing view of the whole system: a **landing/overview home**, recorded agent runs,
per-run execution traces, eval verdicts (with failure attribution + self-eval),
and deterministic replay/bisect. **Mission-control** dark theme, a single emerald
signal accent, Geist type, Framer Motion throughout.

Runs on **port 3001**.

## Design system (the three skills)

The look was built against `.agents/skills/{emil-design-eng, design-taste-frontend, impeccable}`.
The committed decisions (locks):

- **POV (anti-generic):** Sentinel as an *instrument / black-box flight recorder*,
  not generic emerald-on-black SaaS. The brand **hexagon-shield logo**
  (`components/sentinel/Logo.tsx`: `SentinelMark` / `SentinelEmblem` / `SentinelLockup`,
  reproduced from `sentinel_logo.svg`, themeable via currentColor) is the recurring
  motif: nav mark, an animated radar-sweep emblem in the hero, footer lockup, favicon
  (`app/icon.svg`), and a faint `.hexmesh` background texture.
- **Theme lock:** one green-tinted near-black canvas (`#06090A`). **Accent lock:** one
  emerald accent (`#34E5B0`); red/amber appear **only** as real verdict state.
- **Type:** **Bricolage Grotesque Variable** (display, via
  `@fontsource-variable/bricolage-grotesque/wght.css` — distinctive, deliberately not
  Geist for headlines, to escape the Vercel-clone reflex) + **Geist Sans** (body) +
  **Geist Mono** (telemetry: ids / scores / readouts). All self-hosted, offline-safe.
- **Bolder, not louder (impeccable `bolder` for product):** stronger hierarchy +
  extreme scale (huge mono stat band), instrument-bezel framing (`.bezel` corner ticks,
  not glass), reduced glassmorphism. No theatrics.
- **Motion:** strong ease-out curves (`cubic-bezier(0.23,1,0.32,1)`), durations
  < 300ms for UI, stagger 55ms, springs only for "alive" elements (hero tilt).
  **Every reveal is paint-time CSS** (`motion-safe:animate-fade-up`), never gated on
  JS-mount opacity or a scroll observer, so content is visible even before hydration
  (the home hero, the loop, recent verdicts, and `PageTransition` were all converted
  off framer `initial="hidden"` after a headless capture caught them shipping blank).
  Counters/rings also render their real value if the count-up never fires.
  `prefers-reduced-motion` collapses movement (globals.css).
- **Bans honored:** zero em-dashes in visible copy (use `-` / `.` / `,`), no gradient
  text, no AI-purple, no fake `<div>` screenshots (the hero uses a **real** component
  preview: `ReliabilityRing` + live verdict chips), radius cap 16px on surfaces.

## Stack

- **Next.js 16 App Router** (Turbopack builds; React 18.3 — Next 16 supports `^18.2`).
  Server components fetch; client components animate. `params`/`searchParams` are
  **Promises** (Next 15+), awaited in every page.
- **Tailwind CSS** with a small hand-rolled **shadcn-style** primitive set
  (`components/ui/*`) — built by hand rather than via the shadcn CLI so the build
  needs no network. Uses `class-variance-authority` + `clsx` + `tailwind-merge`.
- **Framer Motion** for all animation; **lucide-react** icons (the project already
  depends on it, so it is the allowed family).
- **geist** font package for Geist Sans/Mono (offline-safe, no `next/font/google`).

## Key Files

```
dashboard/
├── package.json            scripts: dev/build/start (port 3001), lint, typecheck, format, test (=tsc)
├── tailwind.config.ts      mission-control palette: canvas #070809, surface #101315, emerald accent + verdict state colours + emil easing curves (card/border tokens kept as back-compat aliases)
├── app/
│   ├── layout.tsx          dark shell + grain overlay + Geist vars + SiteHeader (Suspense-wrapped)
│   ├── globals.css         theme tokens, aurora/grain/dotgrid utilities, easing vars, reduced-motion block
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
│       ├── ReliabilityRing.tsx  animated SVG pass-rate gauge (hero showpiece)
│       ├── motion.tsx           PageTransition / HoverCard / Tilt (mouse-spring) / stagger variants + EASE_OUT
│       ├── AnimatedCounter / ConfidenceBar / DataSourceBadge / EmptyState / PageHeader / SiteHeader
│       └── views/               HomeLanding (the landing showpiece) + *View client components per screen
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

Two layers (see `lib/api.ts`):

**Public URLs** — used for human-clickable links (replay deep-link, Langfuse).
Defaults are the live production URLs; override with `NEXT_PUBLIC_*`:

| Env var | Default |
|---|---|
| `NEXT_PUBLIC_FLIGHT_RECORDER_URL` | `https://flight.ahmedxsaad.me` |
| `NEXT_PUBLIC_EVAL_ENGINE_URL` | `https://eval.ahmedxsaad.me` |
| `NEXT_PUBLIC_FORGE_REMOTE_URL` | `https://remote.ahmedxsaad.me` |
| `NEXT_PUBLIC_LANGFUSE_URL` | `https://langfuse.ahmedxsaad.me` |

**Internal bases** — used for **server-side fetches only** (never sent to the
browser); default to the public URL when unset:

| Env var | Purpose | VM value |
|---|---|---|
| `FLIGHT_RECORDER_INTERNAL_URL` | server-fetch `/runs`, `/runs/{id}`, `/replay`, `/bisect` | `http://localhost:8001` |
| `EVAL_ENGINE_INTERNAL_URL` | server-fetch `/verdicts[/{id}]` | `http://localhost:8000` |

On the Azure VM the `sentinel-dashboard` systemd unit sets the two internal vars to
localhost so the dashboard talks to the services directly (real data, no tunnel hop)
while clickable links stay public.

(All read in TS, not Python, so `check_docs.py`'s `.env.example` parity check — which
only scans `.py` — does not require them.)

## Deployment (Azure VM)

- Built (`pnpm --filter dashboard build`) then served by the **`sentinel-dashboard`**
  systemd unit: `node node_modules/next/dist/bin/next start -p 3001`, enabled +
  auto-restart, logs to `/srv/sentinel/logs/dashboard.log`.
- Exposed at **`https://dashboard.ahmedxsaad.me`** via the `sentinel` Cloudflare
  tunnel: an ingress rule `dashboard.ahmedxsaad.me → http://localhost:3001` in
  `~/.cloudflared/config.yml` + a proxied DNS CNAME
  (`cloudflared tunnel route dns sentinel dashboard.ahmedxsaad.me`).
- The zone enforces a Cloudflare **managed/bot challenge**, so `curl` gets
  `403 cf-mitigated: challenge` while browsers pass — a shell 403 is **not** an outage.
- After a rebuild: `sudo systemctl restart sentinel-dashboard`.

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
