/**
 * TypeScript mirror of `schema.py`.
 *
 * The single source of truth for cross-package data types on the TypeScript side
 * (dashboard + Forge app). Every interface here mirrors exactly one Pydantic
 * model in `schema.py` and must stay in sync with it — when a field changes in
 * `schema.py`, change it here in the same commit (enforced by review; see the
 * package CLAUDE.md "Critical Rule").
 *
 * Conventions:
 *  - Python `datetime`        -> `string` (ISO 8601, as emitted by Pydantic JSON)
 *  - Python `dict[str, Any]`  -> `Record<string, unknown>`
 *  - Python `X | None`        -> `X | null`
 *  - Python `float` / `int`   -> `number`
 */

// ─── Shared literal types ──────────────────────────────────────────────────────

/** mirrors schema.py: StepKind */
export type StepKind = "llm_call" | "tool_call" | "decision" | "state_snapshot";

/** mirrors schema.py: FlightMode */
export type FlightMode = "record" | "replay" | "passthrough";

/** mirrors schema.py: RunStatus */
export type RunStatus = "running" | "completed" | "failed" | "aborted";

/** mirrors schema.py: VerdictLabel */
export type VerdictLabel = "pass" | "fail" | "uncertain";

/** mirrors schema.py: SeverityLevel */
export type SeverityLevel = "critical" | "high" | "medium" | "low";

// ─── Flight Recorder — trace & audit (UC2) ─────────────────────────────────────

/** mirrors schema.py: StepMetadata */
export interface StepMetadata {
  /** LLM model identifier for llm_call steps. */
  model_id: string | null;
  /** Tool/function name for tool_call steps. */
  tool_name: string | null;
  /** Version string of the tool/MCP server that handled the call. */
  tool_version: string | null;
  /** Wall-clock latency of the step in milliseconds. */
  latency_ms: number | null;
  /** LLM sampling parameters (temperature, top_p, max_tokens, ...). */
  sampling_params: Record<string, unknown> | null;
}

/** mirrors schema.py: AuditBlock */
export interface AuditBlock {
  /** payload_hash of the previous record (chain link); genesis is all-zero. */
  prev_hash: string;
  /** SHA-256 of this record's canonical JSON, e.g. "sha256:...". */
  payload_hash: string;
  /** HMAC-SHA256 of payload_hash signed with AUDIT_HMAC_KEY. */
  hmac: string;
}

/** mirrors schema.py: TraceRecord */
export interface TraceRecord {
  /** UUID of the run this step belongs to. */
  run_id: string;
  /** UUID uniquely identifying this step. */
  step_id: string;
  /** 0-based position of this step within the run. */
  sequence: number;
  /** UTC timestamp when the step was recorded (ISO 8601). */
  timestamp: string;
  /** The kind of boundary event captured. */
  kind: StepKind;
  /** Raw input payload sent at this step. */
  input: Record<string, unknown>;
  /** Raw output payload received at this step. */
  output: Record<string, unknown>;
  /** Provenance and timing for this step. */
  metadata: StepMetadata;
  /** Hash-chained, HMAC-signed audit link for this step. */
  audit: AuditBlock;
}

/** mirrors schema.py: RunManifest */
export interface RunManifest {
  /** UUID of this run. */
  run_id: string;
  /** Identifier of the agent that produced the run. */
  agent_id: string;
  /** Identifier of the task/scenario the agent was given. */
  task_id: string;
  /** Recorder mode the run executed under. */
  flight_mode: FlightMode;
  /** Reference to the cassette blob in storage (null until recorded). */
  cassette_id: string | null;
  /** Number of recorded steps in the run. */
  step_count: number;
  /** Lifecycle status of the run. */
  status: RunStatus;
  /** UTC timestamp when the run started (ISO 8601). */
  started_at: string;
  /** UTC timestamp when the run finished (null while running). */
  completed_at: string | null;
}

// ─── Eval Engine — verdicts & attribution (UC1) ────────────────────────────────

/** mirrors schema.py: DimensionScore */
export interface DimensionScore {
  /** Normalized dimension score in [0, 1]. */
  score: number;
  /** Human-readable justification for the score. */
  reason: string;
  /** Judge confidence in this dimension score, in [0, 1]. */
  confidence: number;
}

/** mirrors schema.py: FailureAttribution */
export interface FailureAttribution {
  /** 0-based index of the step blamed for the failure. */
  step: number;
  /** Component attributed (e.g. "retrieval", "planning", "execution"). */
  component: string;
  /** Explanation of how this step caused the failure. */
  description: string;
  /** Confidence in this attribution, in [0, 1]. */
  confidence: number;
}

/** mirrors schema.py: SelfEvaluation */
export interface SelfEvaluation {
  /** Overall confidence the judge has in its verdict, in [0, 1]. */
  judge_confidence: number;
  /** The judge's critique of its own reasoning. */
  self_critique: string;
  /** True if this verdict needs human review. */
  flag_for_human: boolean;
}

/** mirrors schema.py: EvalVerdict */
export interface EvalVerdict {
  /** UUID of the run that was evaluated. */
  run_id: string;
  /** 0-based trial index within a pass^k evaluation batch. */
  trial_number: number;
  /** Overall pass/fail/uncertain outcome. */
  verdict: VerdictLabel;
  /** Per-dimension rubric scores keyed by dimension name. */
  dimensions: Record<string, DimensionScore>;
  /** Which step/component caused the failure (null when verdict is pass). */
  failure_attribution: FailureAttribution | null;
  /** The judge's confidence and self-critique for this verdict. */
  self_evaluation: SelfEvaluation;
  /** Deep link to the deterministic replay of this run. */
  replay_link: string;
  /** Concrete next step for a human. */
  recommended_action: string;
}

// ─── Retrieval & explainability (xqdrant) ──────────────────────────────────────

/** mirrors schema.py: Attribution */
export interface Attribution {
  /** Per-embedding-dimension contribution to the similarity score. */
  dims: Record<string, number>;
  /** Per-term contribution to the match (lexical explainability). */
  terms: Record<string, number>;
  /** Score gap between this hit and the next-best hit; smaller is more ambiguous. */
  confidence_margin: number;
}

/** mirrors schema.py: SearchResult */
export interface SearchResult {
  /** Identifier of the matched document (incident or runbook). */
  id: string;
  /** The matched document's text content. */
  text: string;
  /** Similarity score (cosine) for this hit. */
  score: number;
  /** Explainability breakdown for this hit. */
  attribution: Attribution;
}

// ─── UC3 Atlassian agent output ────────────────────────────────────────────────

/** mirrors schema.py: RcaDraft */
export interface RcaDraft {
  /** The proposed root cause of the incident. */
  root_cause_hypothesis: string;
  /** Specific evidence (similar incidents, runbook excerpts) backing the hypothesis. */
  evidence: string[];
  /** Why the proposed severity was chosen. */
  severity_rationale: string;
  /** Proposed incident severity level. */
  proposed_severity: SeverityLevel;
  /** Team the incident should be assigned to, based on similar past patterns. */
  proposed_assignee_team: string;
  /** IDs of suspected semantic-duplicate incidents (empty if none found). */
  duplicate_check: string[];
  /** Topics with no matching runbook (drive Confluence stub creation). */
  knowledge_gaps: string[];
  /** Agent's confidence in this draft, in [0, 1]. */
  confidence_score: number;
}

/** mirrors schema.py: DuplicateVerdict */
export interface DuplicateVerdict {
  /** True when the incident is judged a true semantic duplicate of a past one. */
  is_duplicate: boolean;
  /** Incident id of the matched duplicate (null when is_duplicate is false). */
  duplicate_of: string | null;
  /** Judge confidence in the duplicate verdict, in [0, 1]. */
  confidence: number;
  /** Why the incident is or is not a duplicate (semantic, not lexical, reasoning). */
  rationale: string;
  /** Polite reporter-facing message to post as a Jira comment when confident. */
  explanation: string;
  /** Ids of near-miss incidents to surface for human review (empty if none). */
  candidates: string[];
}
