/**
 * Types shared with the `atlassian-remote` backend.
 *
 * These mirror the relevant subset of `trace-core/src/trace_core/schema.ts`
 * (`Attribution`, `SearchResult`, `RcaDraft`, `SeverityLevel`) plus the
 * backend-local response envelopes (`AnalyzeResult`, `SearchResponse`,
 * `EmbedResponse`). trace-core has no published npm name, so the agent restates
 * the contract here — keep it in sync with `schema.ts` when fields change.
 */

/** mirrors trace_core.SeverityLevel */
export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low';

/** mirrors trace_core.Attribution — xqdrant explainability breakdown. */
export interface Attribution {
  dims: Record<string, number>;
  terms: Record<string, number>;
  confidence_margin: number;
}

/** mirrors trace_core.SearchResult — one ranked vector-search hit. */
export interface SearchResult {
  id: string;
  text: string;
  score: number;
  attribution: Attribution;
}

/** mirrors trace_core.RcaDraft — the structured root-cause-analysis draft. */
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

/** Response of the backend `POST /analyze` (atlassian_remote.models.AnalyzeResult). */
export interface AnalyzeResult {
  rca_draft: RcaDraft;
  similar: SearchResult[];
  runbooks: SearchResult[];
  flag_for_human: boolean;
}

/** mirrors trace_core.DuplicateVerdict — the structured semantic-duplicate judgment. */
export interface DuplicateVerdict {
  is_duplicate: boolean;
  duplicate_of: string | null;
  confidence: number;
  rationale: string;
  explanation: string;
  candidates: string[];
}

/** Response of the backend `POST /duplicates` (atlassian_remote.models.DuplicateResult). */
export interface DuplicateResult {
  verdict: DuplicateVerdict;
  similar: SearchResult[];
  flag_for_human: boolean;
}

/** Response of the backend `POST /search`. */
export interface SearchResponse {
  results: SearchResult[];
}

/** Response of the backend `POST /embed`. */
export interface EmbedResponse {
  embeddings: number[][];
}
