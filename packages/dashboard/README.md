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
| `/` | Overview: stats (Total Runs, Pass Rate, pass^k, Flagged), recent verdicts, one-loop pipeline |
| `/runs` | All recorded runs (`GET /runs`) — click a row → trace |
| `/runs/[run_id]` | Execution trace: manifest + staggered step timeline; Replay / View Verdict |
| `/verdicts/[run_id]` | Full verdict: PASS/FAIL/UNCERTAIN hero, per-dimension scores, failure attribution, self-eval, replay link |
| `/replay/[run_id]` | Deterministic replay (`POST /replay`), mid-replay inject, and bisect (`POST /bisect`) |
| `/reliability` | Drift detection + evaluator quality side by side (UC1 §2.3/§2.4) |

Plus `app/api/{replay,bisect}/route.ts` — server-side POST proxies (no browser CORS).

## `?mock=true` — the demo safety net

Append `?mock=true` to **any** page to render from realistic fixtures
(`lib/mock-data.ts`) that match the live API shapes exactly. In live mode, if a
service is unreachable the page automatically falls back to mock data — so a screen
never breaks during judging. A `DataSourceBadge` shows whether you're seeing
`LIVE`, `MOCK DATA`, or `MOCK (fallback)`. All fetches are server-side.

> The eval engine exposes `GET /verdicts` and `GET /verdicts/{run_id}` (reading the
> persisted D1 `eval_verdicts` table), so the home recent-verdicts table and the verdict
> detail screen serve **live** data once any run has been evaluated via `/analyze`.

## Stack

Next.js 16 App Router · Tailwind CSS · hand-rolled shadcn-style primitives
(`components/ui/*`) · Framer Motion · lucide-react. Fonts are self-hosted offline:
**Bricolage Grotesque Variable** (display, `@fontsource-variable`) + **Geist Sans/Mono**
(`geist` package) — no remote font host. Types in `lib/types.ts` mirror `trace-core/schema.ts`.

**Deployed** as the `sentinel-dashboard` systemd unit (`next start -p 3001`) on the Azure VM,
exposed at `https://dashboard.ahmedxsaad.me` via the Cloudflare `sentinel` tunnel.

## Setup

```bash
pnpm --filter dashboard install
pnpm --filter dashboard dev        # dev server on :3001
pnpm --filter dashboard build      # production build
pnpm --filter dashboard typecheck  # tsc --noEmit
pnpm --filter dashboard lint
```

Override public link URLs with `NEXT_PUBLIC_FLIGHT_RECORDER_URL`, `NEXT_PUBLIC_EVAL_ENGINE_URL`,
`NEXT_PUBLIC_FORGE_REMOTE_URL`, `NEXT_PUBLIC_LANGFUSE_URL` (defaults are the live production URLs).

For server-side fetches (data, not links) use `FLIGHT_RECORDER_INTERNAL_URL` and
`EVAL_ENGINE_INTERNAL_URL` — on the VM these point to `http://127.0.0.1:800{1,0}` so
fetches bypass the Cloudflare tunnel. Use `127.0.0.1`, not `localhost` (IPv6 resolution
breaks uvicorn). `FORGE_REMOTE_SECRET` is sent as `X-Sentinel-Secret` on every server-side
fetch to the protected services.
