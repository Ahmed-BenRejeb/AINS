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

// Live service URLs (overridable via env for local dev / self-hosting).
export const FLIGHT_RECORDER_URL =
  process.env.NEXT_PUBLIC_FLIGHT_RECORDER_URL ?? "https://flight.ahmedxsaad.me";
export const EVAL_ENGINE_URL =
  process.env.NEXT_PUBLIC_EVAL_ENGINE_URL ?? "https://eval.ahmedxsaad.me";
export const FORGE_REMOTE_URL =
  process.env.NEXT_PUBLIC_FORGE_REMOTE_URL ?? "https://remote.ahmedxsaad.me";
export const LANGFUSE_URL =
  process.env.NEXT_PUBLIC_LANGFUSE_URL ?? "https://langfuse.ahmedxsaad.me";

const FETCH_TIMEOUT_MS = 5000;

/** Fetch JSON with a hard timeout; throws on timeout or non-2xx response. */
async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
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
    const rows = await fetchJson<RunManifestRow[]>(`${FLIGHT_RECORDER_URL}/runs`);
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
      `${FLIGHT_RECORDER_URL}/runs/${encodeURIComponent(runId)}`,
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
      `${EVAL_ENGINE_URL}/verdicts/${encodeURIComponent(runId)}`,
    );
    return live(verdict);
  } catch (err) {
    return fallback(mockVerdict(runId), err);
  }
}

/** Fetch the compact verdict summaries used on the home page (`GET /verdicts`). */
export async function getVerdictSummaries(
  useMock: boolean,
): Promise<Loaded<VerdictSummary[]>> {
  if (useMock) return mock(mockVerdictSummaries());
  try {
    const verdicts = await fetchJson<EvalVerdict[]>(`${EVAL_ENGINE_URL}/verdicts`);
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

  const [runs, verdicts] = await Promise.all([
    getRuns(false),
    getVerdictSummaries(false),
  ]);

  // If neither live source came back, present a clean mock-fallback bundle.
  if (runs.source !== "live" && verdicts.source !== "live") {
    return fallback(
      { stats: mockStats(), summaries: mockVerdictSummaries() },
      runs.error ?? verdicts.error ?? "live services unreachable",
    );
  }

  const summaries = verdicts.data;
  const window = summaries.slice(0, 8);
  const passes = window.filter((v) => v.verdict === "pass").length;
  const stats: OverviewStats = {
    total_runs: runs.data.length || summaries.length,
    pass_rate: window.length ? passes / window.length : 0,
    // pass^k = 1.0 only if every trial in the window passed (all() semantics).
    pass_hat_k: window.length > 0 && passes === window.length ? 1 : 0,
    flagged_for_human: summaries.filter((v) => v.flag_for_human).length,
  };
  const source = runs.source === "live" && verdicts.source === "live" ? "live" : "mock-fallback";
  return { data: { stats, summaries }, source, error: verdicts.error ?? runs.error };
}

// ─── Replay / bisect (POST) ────────────────────────────────────────────────────

/** Trigger a deterministic replay (`POST /replay`). */
export async function postReplay(
  runId: string,
  useMock: boolean,
): Promise<Loaded<ReplayResult>> {
  if (useMock) return mock(mockReplay(runId));
  try {
    const result = await fetchJson<ReplayResult>(`${FLIGHT_RECORDER_URL}/replay`, {
      method: "POST",
      body: JSON.stringify({ run_id: runId }),
    });
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
    const result = await fetchJson<BisectResult>(`${FLIGHT_RECORDER_URL}/bisect`, {
      method: "POST",
      body: JSON.stringify({ good_run_id: goodRunId, bad_run_id: badRunId }),
    });
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
