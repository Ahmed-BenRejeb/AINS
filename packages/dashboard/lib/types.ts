/**
 * Dashboard-side type definitions.
 *
 * The shared cross-package shapes (TraceRecord, EvalVerdict, SearchResult, …) are
 * mirrored from the single source of truth at
 * `packages/trace-core/src/trace_core/schema.ts`. They are duplicated here (rather
 * than imported) because the dashboard is an independent Next.js workspace package
 * with its own tsconfig — keep these in sync with `schema.ts` when it changes.
 *
 * The API-envelope shapes below (RunManifestRow, TraceRecordRow, ReplayResult,
 * BisectResult) match the JSON actually returned by the live services
 * (flight-recorder `:8001`, eval-engine `:8000`).
 */

// ─── Shared literals (mirror schema.ts) ────────────────────────────────────────

export type StepKind = "llm_call" | "tool_call" | "decision" | "state_snapshot";
export type FlightMode = "record" | "replay" | "passthrough";
export type RunStatus = "running" | "completed" | "failed" | "aborted";
export type VerdictLabel = "pass" | "fail" | "uncertain";
export type SeverityLevel = "critical" | "high" | "medium" | "low";

// ─── Eval Engine — verdicts (mirror schema.ts) ─────────────────────────────────

export interface DimensionScore {
  score: number;
  reason: string;
  confidence: number;
}

export interface FailureAttribution {
  step: number;
  component: string;
  description: string;
  confidence: number;
}

export interface SelfEvaluation {
  judge_confidence: number;
  self_critique: string;
  flag_for_human: boolean;
}

export interface EvalVerdict {
  run_id: string;
  trial_number: number;
  verdict: VerdictLabel;
  dimensions: Record<string, DimensionScore>;
  failure_attribution: FailureAttribution | null;
  self_evaluation: SelfEvaluation;
  replay_link: string;
  recommended_action: string;
}

// ─── Retrieval (mirror schema.ts) ──────────────────────────────────────────────

export interface Attribution {
  dims: Record<string, number>;
  terms: Record<string, number>;
  confidence_margin: number;
}

export interface SearchResult {
  id: string;
  text: string;
  score: number;
  attribution: Attribution;
}

// ─── UC3 agent output (mirror schema.ts) ───────────────────────────────────────

export interface RcaDraft {
  root_cause_hypothesis: string;
  evidence: string[];
  severity_rationale: string;
  proposed_severity: SeverityLevel;
  proposed_assignee_team: string;
  duplicate_check: string[];
  knowledge_gaps: string[];
  confidence_score: number;
}

export interface AnalyzeResult {
  run_id: string;
  rca_draft: RcaDraft;
  similar: SearchResult[];
  runbooks: SearchResult[];
  flag_for_human: boolean;
  eval_verdict: EvalVerdict | null;
  replay_link: string;
}

// ─── Flight Recorder — live API envelopes ──────────────────────────────────────

/**
 * A row from the `run_manifests` D1 table, as returned by `GET /runs`.
 * Mirrors `flight_recorder.manifest`'s serialised RunManifest.
 */
export interface RunManifestRow {
  run_id: string;
  agent_id: string;
  task_id: string;
  flight_mode: FlightMode | string;
  cassette_id: string | null;
  step_count: number;
  status: RunStatus | string;
  started_at: string;
  completed_at: string | null;
}

/**
 * A row from the `trace_records` D1 table, as returned by `GET /runs/{run_id}`.
 * Note: latency is not persisted to D1 (metadata_json only carries the hmac
 * algorithm), so `latency_ms` is optional — the timeline degrades gracefully.
 */
export interface TraceRecordRow {
  id: string;
  run_id: string;
  sequence: number;
  kind: StepKind | string;
  timestamp_utc: string;
  payload_hash: string;
  prev_hash: string;
  hmac: string;
  input_preview: string;
  output_preview: string;
  metadata_json: string;
  latency_ms?: number | null;
}

/** Response of `GET /runs/{run_id}`. */
export interface RunDetail {
  run_id: string;
  manifest: RunManifestRow | null;
  trace: TraceRecordRow[];
}

export interface Divergence {
  step_key: string;
  reason: string;
}

/** Response of `POST /replay`. */
export interface ReplayResult {
  run_id: string;
  recorded_steps: number;
  live_call_count: number;
  diverged: boolean;
  divergences: Divergence[];
}

/** Response of `POST /bisect`. */
export interface BisectResult {
  good_run_id: string;
  bad_run_id: string;
  identical: boolean;
  first_diverging_step: number | null;
  reason: string | null;
  good_step_key: string | null;
  bad_step_key: string | null;
  good_output: Record<string, unknown> | null;
  bad_output: Record<string, unknown> | null;
}

// ─── Dashboard view models ─────────────────────────────────────────────────────

/** Where a payload came from — drives the small data-source badge in the header. */
export type DataSource = "live" | "mock" | "mock-fallback";

/** Wraps any fetched payload with its provenance so the UI can be honest. */
export interface Loaded<T> {
  data: T;
  source: DataSource;
  /** Present when a live fetch failed and we fell back to mock data. */
  error?: string;
}

/** Compact home-page verdict row (joins a verdict with its flag/timestamp). */
export interface VerdictSummary {
  run_id: string;
  verdict: VerdictLabel;
  flag_for_human: boolean;
  timestamp: string;
}

/** Aggregate metrics shown in the home-page stats row. */
export interface OverviewStats {
  total_runs: number;
  pass_rate: number; // 0–1
  pass_hat_k: number; // 0–1, last 8 trials
  flagged_for_human: number;
}
