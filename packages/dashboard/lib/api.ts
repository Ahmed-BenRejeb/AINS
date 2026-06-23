/**
 * Data access for the Sentinel dashboard.
 *
 * Every accessor returns a `Loaded<T>` carrying both the payload and its
 * provenance (`live` | `mock` | `mock-fallback`). Behaviour:
 *
 *   • `?mock=true`  → always returns the fixtures in lib/mock-data.ts.
 *   • otherwise     → fetches the live service; on ANY failure (network, non-2xx,
 *                     timeout, or an endpoint the service doesn't expose) it falls
 *                     back to mock data and tags the result `mock-fallback`.
 *
 * This makes every screen render in both modes (the demo safety net) while staying
 * honest — the header badge tells you whether you're looking at live or mock data.
 *
 * These functions run server-side (Server Components + route handlers), so calling
 * the live APIs is server-to-server: no browser CORS, no secrets in the client.
 */

import {
  mockBisect,
  mockReplay,
  mockRunDetail,
  mockRuns,
  mockStats,
  mockVerdict,
  mockVerdictSummaries,
} from "./mock-data";
import type {
  BisectResult,
  EvalVerdict,
  Loaded,
  OverviewStats,
  ReplayResult,
  RunDetail,
  RunManifestRow,
  VerdictLabel,
  VerdictSummary,
} from "./types";

// Public service URLs — used for human-clickable links (replay deep-link, Langfuse).
// Overridable via env for local dev / self-hosting.
export const FLIGHT_RECORDER_URL =
  process.env.NEXT_PUBLIC_FLIGHT_RECORDER_URL ?? "https://flight.ahmedxsaad.me";
export const EVAL_ENGINE_URL =
  process.env.NEXT_PUBLIC_EVAL_ENGINE_URL ?? "https://eval.ahmedxsaad.me";
export const FORGE_REMOTE_URL =
  process.env.NEXT_PUBLIC_FORGE_REMOTE_URL ?? "https://remote.ahmedxsaad.me";
export const LANGFUSE_URL =
  process.env.NEXT_PUBLIC_LANGFUSE_URL ?? "https://langfuse.ahmedxsaad.me";
export const DASHBOARD_URL =
  process.env.NEXT_PUBLIC_DASHBOARD_URL ?? "https://dashboard.ahmedxsaad.me";

// Internal base URLs for server-side fetches (never sent to the browser). On the
// Azure VM these point at localhost so the dashboard talks to the services directly
// (faster, and avoids the public tunnel hop), while the clickable links above stay
// public. Default to the public URL when unset (e.g. local dev).
const FLIGHT_RECORDER_API =
  process.env.FLIGHT_RECORDER_INTERNAL_URL ?? FLIGHT_RECORDER_URL;
const EVAL_ENGINE_API = process.env.EVAL_ENGINE_INTERNAL_URL ?? EVAL_ENGINE_URL;

const FETCH_TIMEOUT_MS = 5000;
// Replay/bisect re-drive a whole cassette, so they can legitimately take longer
// than a list/detail GET. Give those POSTs a wider budget before falling back.
const REPLAY_TIMEOUT_MS = 30000;

/** Fetch JSON with a hard timeout; throws on timeout or non-2xx response. */
async function fetchJson<T>(
  url: string,
  init?: RequestInit,
  timeoutMs: number = FETCH_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) {
      throw new Error(`${url} → HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

function live<T>(data: T): Loaded<T> {
  return { data, source: "live" };
}
function mock<T>(data: T): Loaded<T> {
  return { data, source: "mock" };
}
function fallback<T>(data: T, error: unknown): Loaded<T> {
  return {
    data,
    source: "mock-fallback",
    error: error instanceof Error ? error.message : String(error),
  };
}

const VERDICT_LABELS: ReadonlySet<string> = new Set(["pass", "fail", "uncertain"]);

function coerceVerdict(value: unknown): VerdictLabel {
  return typeof value === "string" && VERDICT_LABELS.has(value)
    ? (value as VerdictLabel)
    : "uncertain";
}

// ─── Runs ──────────────────────────────────────────────────────────────────────

/** List all recorded runs (`GET /runs`), newest first. */
export async function getRuns(useMock: boolean): Promise<Loaded<RunManifestRow[]>> {
  if (useMock) return mock(mockRuns);
  try {
    const rows = await fetchJson<RunManifestRow[]>(`${FLIGHT_RECORDER_API}/runs`);
    return live(Array.isArray(rows) ? rows : []);
  } catch (err) {
    return fallback(mockRuns, err);
  }
}

/** Fetch one run's manifest + ordered trace (`GET /runs/{run_id}`). */
export async function getRunDetail(
  runId: string,
  useMock: boolean,
): Promise<Loaded<RunDetail>> {
  if (useMock) return mock(mockRunDetail(runId));
  try {
    const detail = await fetchJson<RunDetail>(
      `${FLIGHT_RECORDER_API}/runs/${encodeURIComponent(runId)}`,
    );
    return live(detail);
  } catch (err) {
    return fallback(mockRunDetail(runId), err);
  }
}

// ─── Verdicts ────────────────────────────────────────────────────────────────
// The eval engine currently exposes /health + POST /evaluate only (no GET list).
// We optimistically try GET /verdicts and GET /verdicts/{id} so the UI lights up
// automatically if those endpoints are added; until then it cleanly falls back.

/** Fetch one run's verdict (`GET /verdicts/{run_id}`). */
export async function getVerdict(
  runId: string,
  useMock: boolean,
): Promise<Loaded<EvalVerdict>> {
  if (useMock) return mock(mockVerdict(runId));
  try {
    const verdict = await fetchJson<EvalVerdict>(
      `${EVAL_ENGINE_API}/verdicts/${encodeURIComponent(runId)}`,
    );
    return live(verdict);
  } catch (err) {
    return fallback(mockVerdict(runId), err);
  }
}

/** Fetch the compact verdict summaries used on the home page (`GET /verdicts`). */
export async function getVerdictSummaries(
  useMock: boolean,
  limit: number = 50,
): Promise<Loaded<VerdictSummary[]>> {
  if (useMock) return mock(mockVerdictSummaries());
  try {
    const verdicts = await fetchJson<EvalVerdict[]>(
      `${EVAL_ENGINE_API}/verdicts?limit=${limit}`,
    );
    const summaries: VerdictSummary[] = verdicts.map((v) => ({
      run_id: v.run_id,
      verdict: coerceVerdict(v.verdict),
      flag_for_human: v.self_evaluation?.flag_for_human ?? false,
      timestamp: (v as unknown as { created_at?: string }).created_at ?? new Date().toISOString(),
    }));
    return live(summaries);
  } catch (err) {
    return fallback(mockVerdictSummaries(), err);
  }
}

// ─── Overview (home page) ──────────────────────────────────────────────────────

export interface Overview {
  stats: OverviewStats;
  summaries: VerdictSummary[];
}

/**
 * Compose the home-page overview. Prefers live `/runs` for the run count and the
 * recent-verdict table; computes pass-rate / pass^k from whatever verdicts are
 * available. Any failure of either source degrades the whole bundle to mock.
 */
export async function getOverview(useMock: boolean): Promise<Loaded<Overview>> {
  if (useMock) {
    return mock({ stats: mockStats(), summaries: mockVerdictSummaries() });
  }

  let [runs, verdicts] = await Promise.all([
    getRuns(false),
    getVerdictSummaries(false, 200),
  ]);

  // Cold-start absorb: if BOTH fetches missed on the first try (e.g. a service is
  // still warming right after a restart), wait briefly and retry once before giving
  // up — so the first page load shows real data rather than flashing empty.
  if (runs.source !== "live" && verdicts.source !== "live") {
    await new Promise((resolve) => setTimeout(resolve, 600));
    [runs, verdicts] = await Promise.all([getRuns(false), getVerdictSummaries(false, 200)]);
  }

  // Live mode: if neither source came back, present an HONEST EMPTY state, not mock
  // fixtures. Showing fabricated demo numbers on a live page (e.g. during a brief
  // service restart) is misleading — better to render zeros + an empty list and let
  // the "fallback" badge + EmptyState say "live data unavailable". Rich mock fixtures
  // are reserved for explicit ?mock=true.
  if (runs.source !== "live" && verdicts.source !== "live") {
    return fallback(
      {
        stats: { total_runs: 0, pass_rate: 0, pass_hat_k: 0, flagged_for_human: 0 },
        summaries: [],
      },
      runs.error ?? verdicts.error ?? "live services unreachable",
    );
  }

  // Group verdicts by run_id (a run can have many trials, e.g. a pass^k sweep) so
  // metrics are per-task, not per-row — otherwise a few k=8 sweeps dominate and the
  // pass rate reads like a coin flip. Summaries arrive newest-first.
  const byRun = new Map<string, VerdictSummary[]>();
  for (const v of verdicts.data) {
    const trials = byRun.get(v.run_id) ?? [];
    trials.push(v);
    byRun.set(v.run_id, trials);
  }
  const runIds = [...byRun.keys()];
  const evaluated = runIds.length;
  let latestPass = 0; // runs whose most-recent verdict is pass
  let allTrialsPass = 0; // runs where EVERY recorded trial passed (true pass^k)
  let flaggedRuns = 0;
  for (const id of runIds) {
    const trials = byRun.get(id) ?? [];
    if (trials[0]?.verdict === "pass") latestPass += 1;
    if (trials.length > 0 && trials.every((t) => t.verdict === "pass")) allTrialsPass += 1;
    if (trials.some((t) => t.flag_for_human)) flaggedRuns += 1;
  }
  const stats: OverviewStats = {
    total_runs: runs.data.length || evaluated,
    // Per-task pass rate: fraction of evaluated runs whose latest verdict is pass.
    pass_rate: evaluated ? latestPass / evaluated : 0,
    // True pass^k: fraction of runs where ALL recorded trials passed (all() semantics).
    pass_hat_k: evaluated ? allTrialsPass / evaluated : 0,
    flagged_for_human: flaggedRuns,
  };
  // Recent-verdicts table: the latest verdict per run (deduped), newest first.
  const recent = runIds.map((id) => (byRun.get(id) ?? [])[0]).filter(Boolean) as VerdictSummary[];
  const source = runs.source === "live" && verdicts.source === "live" ? "live" : "mock-fallback";
  return { data: { stats, summaries: recent }, source, error: verdicts.error ?? runs.error };
}

// ─── Replay / bisect (POST) ────────────────────────────────────────────────────

/** Trigger a deterministic replay (`POST /replay`). */
export async function postReplay(
  runId: string,
  useMock: boolean,
): Promise<Loaded<ReplayResult>> {
  if (useMock) return mock(mockReplay(runId));
  try {
    const result = await fetchJson<ReplayResult>(
      `${FLIGHT_RECORDER_API}/replay`,
      { method: "POST", body: JSON.stringify({ run_id: runId }) },
      REPLAY_TIMEOUT_MS,
    );
    return live(result);
  } catch (err) {
    return fallback(mockReplay(runId), err);
  }
}

/** Bisect two runs to find the first divergence (`POST /bisect`). */
export async function postBisect(
  goodRunId: string,
  badRunId: string,
  useMock: boolean,
): Promise<Loaded<BisectResult>> {
  if (useMock) return mock(mockBisect);
  try {
    const result = await fetchJson<BisectResult>(
      `${FLIGHT_RECORDER_API}/bisect`,
      { method: "POST", body: JSON.stringify({ good_run_id: goodRunId, bad_run_id: badRunId }) },
      REPLAY_TIMEOUT_MS,
    );
    return live(result);
  } catch (err) {
    return fallback(mockBisect, err);
  }
}

/** Parse the `?mock=` search param into a boolean (true only for "true"/"1"). */
export function isMock(searchParams?: { mock?: string | string[] }): boolean {
  const raw = searchParams?.mock;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value === "true" || value === "1";
}
