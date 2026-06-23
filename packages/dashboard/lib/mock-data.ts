/**
 * Realistic fixture data for `?mock=true` (the demo safety net).
 *
 * Every shape here matches the live API responses exactly (see lib/types.ts and
 * trace-core/schema.ts), so a screen rendered from mock data is indistinguishable
 * in structure from one rendered from the real services. The narrative is a small
 * fleet of Atlassian-incident RCA runs evaluated by the eval engine — a mix of
 * pass / fail / uncertain so judges can see every verdict state at once.
 */

import type {
  AnalyzeResult,
  BisectResult,
  DriftReport,
  EvalVerdict,
  EvaluatorQuality,
  OverviewStats,
  ReplayResult,
  RunDetail,
  RunManifestRow,
  TraceRecordRow,
  VerdictSummary,
} from "./types";

/** Stable run ids (UUID-shaped) used across runs, traces, and verdicts. */
const RUN_IDS = {
  pass1: "8f3a1c2e-4b7d-4e91-a2c5-6d8f0b1e3a47",
  fail1: "2c9e7b40-1a3f-4d62-8e05-9b4c7a1f0d23",
  uncertain1: "a1b2c3d4-e5f6-4789-90ab-cdef01234567",
  pass2: "5d6e7f80-9a1b-42c3-84d5-e6f708192a3b",
  pass3: "0f1e2d3c-4b5a-4968-8776-554433221100",
  fail2: "9988aabb-ccdd-4eef-8011-223344556677",
} as const;

function isoMinutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

// ─── Runs (GET /runs) ──────────────────────────────────────────────────────────

export const mockRuns: RunManifestRow[] = [
  {
    run_id: RUN_IDS.fail2,
    agent_id: "sentinel-rca-agent",
    task_id: "AO-218 · checkout latency spike",
    flight_mode: "record",
    cassette_id: "sentinel-cassettes/9988aabb.json",
    step_count: 6,
    status: "completed",
    started_at: isoMinutesAgo(4),
    completed_at: isoMinutesAgo(4),
  },
  {
    run_id: RUN_IDS.uncertain1,
    agent_id: "sentinel-rca-agent",
    task_id: "AO-205 · auth token refresh loop",
    flight_mode: "record",
    cassette_id: "sentinel-cassettes/a1b2c3d4.json",
    step_count: 5,
    status: "completed",
    started_at: isoMinutesAgo(19),
    completed_at: isoMinutesAgo(19),
  },
  {
    run_id: RUN_IDS.pass1,
    agent_id: "sentinel-rca-agent",
    task_id: "AO-201 · DB connection pool exhausted",
    flight_mode: "record",
    cassette_id: "sentinel-cassettes/8f3a1c2e.json",
    step_count: 5,
    status: "completed",
    started_at: isoMinutesAgo(42),
    completed_at: isoMinutesAgo(42),
  },
  {
    run_id: RUN_IDS.fail1,
    agent_id: "sentinel-rca-agent",
    task_id: "AO-198 · webhook delivery failures",
    flight_mode: "record",
    cassette_id: "sentinel-cassettes/2c9e7b40.json",
    step_count: 5,
    status: "completed",
    started_at: isoMinutesAgo(73),
    completed_at: isoMinutesAgo(73),
  },
  {
    run_id: RUN_IDS.pass2,
    agent_id: "sentinel-rca-agent",
    task_id: "AO-187 · stale cache served to users",
    flight_mode: "record",
    cassette_id: "sentinel-cassettes/5d6e7f80.json",
    step_count: 5,
    status: "completed",
    started_at: isoMinutesAgo(128),
    completed_at: isoMinutesAgo(128),
  },
  {
    run_id: RUN_IDS.pass3,
    agent_id: "sentinel-rca-agent",
    task_id: "AO-176 · rate-limit 429s from upstream",
    flight_mode: "record",
    cassette_id: "sentinel-cassettes/0f1e2d3c.json",
    step_count: 5,
    status: "completed",
    started_at: isoMinutesAgo(214),
    completed_at: isoMinutesAgo(214),
  },
];

// ─── Trace records (GET /runs/{run_id}) ────────────────────────────────────────

function step(
  runId: string,
  sequence: number,
  kind: TraceRecordRow["kind"],
  inputPreview: string,
  outputPreview: string,
  latencyMs: number,
): TraceRecordRow {
  return {
    id: `${runId.slice(0, 8)}-step-${sequence}`,
    run_id: runId,
    sequence,
    kind,
    timestamp_utc: isoMinutesAgo(42 - sequence),
    payload_hash: `sha256:${(sequence * 7919).toString(16).padStart(8, "0")}…`,
    prev_hash:
      sequence === 0
        ? "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        : `sha256:${((sequence - 1) * 7919).toString(16).padStart(8, "0")}…`,
    hmac: `hmac:${(sequence * 104729).toString(16).slice(0, 12)}`,
    input_preview: inputPreview,
    output_preview: outputPreview,
    metadata_json: JSON.stringify({ hmac_algorithm: "sha256" }),
    latency_ms: latencyMs,
  };
}

const RCA_FLOW: Array<
  [TraceRecordRow["kind"], string, string, number]
> = [
  [
    "decision",
    "fetch_incident(key='AO-201')",
    "Loaded incident: summary + ADF description flattened to 1.2k chars",
    38,
  ],
  [
    "llm_call",
    "embed: 'DB connection pool exhausted; HikariCP timeout after 30s…'",
    "768-dim vector [0.013, -0.041, 0.092, …]",
    214,
  ],
  [
    "tool_call",
    "xqdrant.query_points(collection='incidents', limit=5)",
    "5 hits · top score 0.89 · margin 0.07 → AO-142, AO-77, AO-31",
    61,
  ],
  [
    "tool_call",
    "xqdrant.query_points(collection='runbooks', limit=3)",
    "2 hits · top score 0.84 → RB-DB-POOL, RB-LATENCY",
    47,
  ],
  [
    "llm_call",
    "RCA prompt: incident + 5 similar + 2 runbooks → structured RcaDraft",
    '{"root_cause_hypothesis":"Connection pool exhausted under burst load…","confidence_score":0.86}',
    1840,
  ],
];

function buildTrace(runId: string): TraceRecordRow[] {
  return RCA_FLOW.map(([kind, input, output, latency], i) =>
    step(runId, i, kind, input, output, latency),
  );
}

const mockTraces: Record<string, TraceRecordRow[]> = {
  [RUN_IDS.pass1]: buildTrace(RUN_IDS.pass1),
  [RUN_IDS.pass2]: buildTrace(RUN_IDS.pass2),
  [RUN_IDS.pass3]: buildTrace(RUN_IDS.pass3),
  [RUN_IDS.uncertain1]: buildTrace(RUN_IDS.uncertain1),
  [RUN_IDS.fail1]: [
    step(
      RUN_IDS.fail1,
      0,
      "decision",
      "fetch_incident(key='AO-198')",
      "Loaded incident: 'webhook delivery failures, 502s from listener'",
      40,
    ),
    step(
      RUN_IDS.fail1,
      1,
      "llm_call",
      "embed: 'webhook delivery failures 502 listener…'",
      "768-dim vector [0.004, 0.071, -0.022, …]",
      198,
    ),
    step(
      RUN_IDS.fail1,
      2,
      "tool_call",
      "xqdrant.query_points(collection='incidents', limit=5)",
      "5 hits · top score 0.71 · margin 0.01 (ambiguous) → AO-90, AO-12",
      58,
    ),
    step(
      RUN_IDS.fail1,
      3,
      "tool_call",
      "xqdrant.query_points(collection='runbooks', limit=3)",
      "0 hits above threshold (0.75) → no runbook evidence",
      44,
    ),
    step(
      RUN_IDS.fail1,
      4,
      "llm_call",
      "RCA prompt with weak/ambiguous evidence → structured RcaDraft",
      '{"root_cause_hypothesis":"DNS resolution failure","confidence_score":0.58}',
      1610,
    ),
  ],
  [RUN_IDS.fail2]: [
    step(
      RUN_IDS.fail2,
      0,
      "decision",
      "fetch_incident(key='AO-218')",
      "Loaded incident: 'checkout p99 latency spike to 4.2s'",
      41,
    ),
    step(
      RUN_IDS.fail2,
      1,
      "llm_call",
      "embed: 'checkout latency spike p99 4.2s…'",
      "768-dim vector [0.031, -0.018, 0.055, …]",
      221,
    ),
    step(
      RUN_IDS.fail2,
      2,
      "tool_call",
      "xqdrant.query_points(collection='incidents', limit=5)",
      "5 hits · top score 0.82 → AO-150, AO-66",
      63,
    ),
    step(
      RUN_IDS.fail2,
      3,
      "tool_call",
      "xqdrant.query_points(collection='runbooks', limit=3)",
      "1 hit · 0.79 → RB-LATENCY",
      49,
    ),
    step(
      RUN_IDS.fail2,
      4,
      "llm_call",
      "safety pre-filter (llama-guard-3-8b) on draft output",
      "safe=true",
      120,
    ),
    step(
      RUN_IDS.fail2,
      5,
      "llm_call",
      "RCA prompt → structured RcaDraft (proposed_severity='low')",
      '{"root_cause_hypothesis":"Minor GC pause","proposed_severity":"low","confidence_score":0.64}',
      1720,
    ),
  ],
};

// ─── Verdicts (GET /verdicts/{run_id}) ─────────────────────────────────────────

const PASS_VERDICT = (runId: string, trial = 0): EvalVerdict => ({
  run_id: runId,
  trial_number: trial,
  verdict: "pass",
  dimensions: {
    correctness: {
      score: 0.91,
      reason:
        "Root cause (connection-pool exhaustion under burst load) matches the resolved cause of the two highest-scoring similar incidents and the RB-DB-POOL runbook.",
      confidence: 0.9,
    },
    efficiency: {
      score: 0.84,
      reason:
        "Reached a grounded hypothesis in 5 steps with two retrieval calls; no redundant LLM round-trips.",
      confidence: 0.82,
    },
    safety: {
      score: 0.98,
      reason: "Llama-Guard pre-filter passed; no PII leaked, no destructive action proposed.",
      confidence: 0.95,
    },
    reasoning_quality: {
      score: 0.88,
      reason: "Each evidence item is cited and the severity rationale follows from the runbook.",
      confidence: 0.86,
    },
  },
  failure_attribution: null,
  self_evaluation: {
    judge_confidence: 0.89,
    self_critique:
      "Position-bias calibration agreed across both rubric orderings. Confidence is high; the only soft spot is efficiency, where one retrieval call could be merged.",
    flag_for_human: false,
  },
  replay_link: `https://flight.ahmedxsaad.me/replay/${runId}`,
  recommended_action: "No action required. The verdict is a confident pass. Safe to auto-post the RCA comment.",
});

const mockVerdicts: Record<string, EvalVerdict> = {
  [RUN_IDS.pass1]: PASS_VERDICT(RUN_IDS.pass1),
  [RUN_IDS.pass2]: PASS_VERDICT(RUN_IDS.pass2, 1),
  [RUN_IDS.pass3]: PASS_VERDICT(RUN_IDS.pass3, 2),
  [RUN_IDS.fail1]: {
    run_id: RUN_IDS.fail1,
    trial_number: 0,
    verdict: "fail",
    dimensions: {
      correctness: {
        score: 0.22,
        reason:
          "Hypothesis (DNS resolution failure) is not supported by any retrieved incident; the actual pattern points to listener thread-pool saturation.",
        confidence: 0.83,
      },
      efficiency: {
        score: 0.7,
        reason: "Step count is reasonable, but a wasted runbook query returned no usable evidence.",
        confidence: 0.75,
      },
      safety: {
        score: 0.96,
        reason: "No unsafe content; safety pre-filter passed.",
        confidence: 0.94,
      },
      reasoning_quality: {
        score: 0.31,
        reason:
          "The draft asserts a root cause the evidence does not back up, a confident hallucination on thin retrieval.",
        confidence: 0.8,
      },
    },
    failure_attribution: {
      step: 2,
      component: "retrieval",
      description:
        "xqdrant returned an ambiguous match (top score 0.71, margin 0.01) and the runbook query found nothing above threshold. The agent proceeded as if evidence were strong, so the RCA is ungrounded.",
      confidence: 0.84,
    },
    self_evaluation: {
      judge_confidence: 0.81,
      self_critique:
        "Both rubric orderings agreed this is a fail. The retrieval step is the clear culprit; the LLM draft itself is fluent but unsupported.",
      flag_for_human: false,
    },
    replay_link: `https://flight.ahmedxsaad.me/replay/${RUN_IDS.fail1}`,
    recommended_action:
      "Do not post the RCA. Re-run with a lower similarity threshold or seed a runbook for webhook-listener saturation, then re-evaluate.",
  },
  [RUN_IDS.fail2]: {
    run_id: RUN_IDS.fail2,
    trial_number: 0,
    verdict: "fail",
    dimensions: {
      correctness: {
        score: 0.4,
        reason:
          "Root-cause direction (GC pause) is plausible but the proposed severity 'low' contradicts a 4.2s p99 on the checkout path.",
        confidence: 0.78,
      },
      efficiency: {
        score: 0.86,
        reason: "Efficient run; included the safety pre-filter step.",
        confidence: 0.8,
      },
      safety: {
        score: 0.95,
        reason: "Safety pre-filter passed.",
        confidence: 0.92,
      },
      reasoning_quality: {
        score: 0.44,
        reason: "Severity rationale understates customer impact; reasoning is internally inconsistent.",
        confidence: 0.76,
      },
    },
    failure_attribution: {
      step: 5,
      component: "planning",
      description:
        "The final RCA draft proposed severity 'low' for a customer-facing checkout latency spike, a severity-calibration error in the generation step.",
      confidence: 0.79,
    },
    self_evaluation: {
      judge_confidence: 0.77,
      self_critique:
        "Verdict held across calibration passes. The factual hypothesis is acceptable; the failure is severity mis-calibration, which materially affects routing.",
      flag_for_human: true,
    },
    replay_link: `https://flight.ahmedxsaad.me/replay/${RUN_IDS.fail2}`,
    recommended_action:
      "Flag for human triage. Severity is likely high or critical. Confirm impact, then re-run with a severity-calibration hint.",
  },
  [RUN_IDS.uncertain1]: {
    run_id: RUN_IDS.uncertain1,
    trial_number: 0,
    verdict: "uncertain",
    dimensions: {
      correctness: {
        score: 0.62,
        reason:
          "Hypothesis (token-refresh race condition) is partly supported, but two similar incidents disagree on the trigger.",
        confidence: 0.55,
      },
      efficiency: {
        score: 0.8,
        reason: "No wasted steps.",
        confidence: 0.78,
      },
      safety: {
        score: 0.97,
        reason: "Safety pre-filter passed.",
        confidence: 0.93,
      },
      reasoning_quality: {
        score: 0.6,
        reason: "Reasoning is coherent but leans on a single ambiguous retrieval hit.",
        confidence: 0.5,
      },
    },
    failure_attribution: null,
    self_evaluation: {
      judge_confidence: 0.48,
      self_critique:
        "Position-bias calibration flipped the verdict between rubric orderings (pass ⇄ uncertain). Per policy this collapses to 'uncertain' and is flagged for human review.",
      flag_for_human: true,
    },
    replay_link: `https://flight.ahmedxsaad.me/replay/${RUN_IDS.uncertain1}`,
    recommended_action:
      "Human review required. The judge was order-sensitive (position_bias_detected). A reviewer should confirm the root cause before posting.",
  },
};

// ─── Replay / bisect ───────────────────────────────────────────────────────────

/** Mock replay result: the failing webhook run diverges, every other run is clean. */
export function mockReplay(runId: string): ReplayResult {
  // The failing webhook run replays with a divergence; everything else is clean.
  if (runId === RUN_IDS.fail1) {
    return {
      run_id: runId,
      recorded_steps: 5,
      live_call_count: 0,
      diverged: true,
      divergences: [
        {
          step_key: "llm:@cf/meta/llama-3.3-70b-instruct-fp8-fast:a17f…",
          reason: "request not present in cassette (prompt drift since recording)",
        },
      ],
    };
  }
  const known = mockRuns.find((r) => r.run_id === runId);
  return {
    run_id: runId,
    recorded_steps: known?.step_count ?? 5,
    live_call_count: 0,
    diverged: false,
    divergences: [],
  };
}

export const mockBisect: BisectResult = {
  good_run_id: RUN_IDS.pass1,
  bad_run_id: RUN_IDS.fail1,
  identical: false,
  first_diverging_step: 2,
  reason: "retrieval output differs: good run matched RB-DB-POOL (0.89); bad run found no runbook (<0.75)",
  good_step_key: "tool:xqdrant.query_points:incidents:8f3a…",
  bad_step_key: "tool:xqdrant.query_points:incidents:2c9e…",
  good_output: { top_score: 0.89, runbook_hits: 2 },
  bad_output: { top_score: 0.71, runbook_hits: 0 },
};

// ─── Aggregates / accessors ────────────────────────────────────────────────────

/** Compact home-page verdict rows (one per mock run, joined to its verdict). */
export function mockVerdictSummaries(): VerdictSummary[] {
  return mockRuns.map((run) => {
    const v = mockVerdicts[run.run_id];
    return {
      run_id: run.run_id,
      verdict: v ? v.verdict : "uncertain",
      flag_for_human: v ? v.self_evaluation.flag_for_human : false,
      timestamp: run.started_at,
    };
  });
}

/** Aggregate home-page metrics derived from the mock verdicts. */
export function mockStats(): OverviewStats {
  const verdicts = Object.values(mockVerdicts);
  const passes = verdicts.filter((v) => v.verdict === "pass").length;
  const flagged = verdicts.filter((v) => v.self_evaluation.flag_for_human).length;
  return {
    total_runs: mockRuns.length,
    // Per-task pass rate (one verdict per mock run).
    pass_rate: passes / verdicts.length,
    // True pass^k: fraction of runs that passed every trial. The τ-bench headline is
    // that pass@1 is far higher than pass^k — keep the mock honest about that gap.
    pass_hat_k: passes / verdicts.length / 2,
    flagged_for_human: flagged,
  };
}

/** A run's manifest + trace for `/runs/[run_id]`; synthesises a trace for unknown ids. */
export function mockRunDetail(runId: string): RunDetail {
  const manifest = mockRuns.find((r) => r.run_id === runId) ?? null;
  const trace = mockTraces[runId] ?? buildTrace(runId);
  return { run_id: runId, manifest, trace };
}

/** A run's verdict for `/verdicts/[run_id]`; defaults to a pass for unknown ids. */
export function mockVerdict(runId: string): EvalVerdict {
  return mockVerdicts[runId] ?? PASS_VERDICT(runId);
}

/** A full `/analyze` envelope (UC3 shape) — kept for reference/completeness. */
export function mockAnalyzeResult(): AnalyzeResult {
  return {
    run_id: RUN_IDS.pass1,
    rca_draft: {
      root_cause_hypothesis:
        "The HikariCP connection pool was exhausted during a traffic burst; queries queued past the 30s timeout and surfaced as 500s.",
      evidence: [
        "AO-142 (score 0.89): identical HikariCP timeout pattern, resolved by raising maxPoolSize.",
        "RB-DB-POOL runbook: 'connection pool exhaustion' playbook matches the symptom set.",
      ],
      severity_rationale:
        "User-facing 500s on the primary API for >10 minutes warrants high severity per the runbook's impact table.",
      proposed_severity: "high",
      proposed_assignee_team: "platform-data",
      duplicate_check: ["AO-142"],
      knowledge_gaps: [],
      confidence_score: 0.86,
    },
    similar: [
      {
        id: "AO-142",
        text: "DB connection pool exhausted; HikariCP timeout after 30s under burst load.",
        score: 0.89,
        attribution: {
          dims: { "412": 0.21, "88": 0.18, "640": 0.15 },
          terms: { pool: 0.31, hikaricp: 0.27, timeout: 0.19 },
          confidence_margin: 0.07,
        },
      },
    ],
    runbooks: [
      {
        id: "RB-DB-POOL",
        text: "Runbook: diagnosing and resolving database connection pool exhaustion.",
        score: 0.84,
        attribution: {
          dims: { "412": 0.19, "640": 0.16 },
          terms: { pool: 0.34, connection: 0.22 },
          confidence_margin: 0.05,
        },
      },
    ],
    flag_for_human: false,
    eval_verdict: PASS_VERDICT(RUN_IDS.pass1),
    replay_link: `https://flight.ahmedxsaad.me/replay/${RUN_IDS.pass1}`,
  };
}

/** Fixture drift report (used for ?mock and as a clean fallback). */
export const mockDrift: DriftReport = {
  baseline_run_count: 5,
  current_run_count: 5,
  pass_rate_baseline: 0.8,
  pass_rate_current: 0.4,
  pass_rate_delta: -0.4,
  mean_score_baseline: 0.86,
  mean_score_current: 0.71,
  dimension_deltas: { correctness: -0.18, efficiency: -0.05, reasoning_quality: -0.12, safety: 0.0 },
  most_shifted_dimension: "correctness",
  semantic_drift: 0.21,
  drift_detected: true,
  drift_score: 0.4,
  summary:
    "Drift detected: pass rate 80% -> 40% (-40%); largest dimension shift: correctness -0.18.",
};

/** Fixture evaluator-quality report (judge-vs-human Cohen's kappa). */
export const mockEvaluatorQuality: EvaluatorQuality = {
  n_cases: 4,
  n_agreements: 3,
  accuracy: 0.75,
  cohen_kappa: 0.6,
  per_label_recall: { pass: 1.0, fail: 0.5 },
  agreement_band: "moderate",
  summary: "Evaluator agreed with 3/4 human gold verdicts (accuracy 75%); Cohen's kappa 0.60 (moderate).",
};

export { RUN_IDS };
