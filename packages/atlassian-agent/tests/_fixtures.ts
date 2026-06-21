/** Shared fixtures for the agent tests (not a test file — no *.test.ts suffix). */

import type { AnalyzeResult, DuplicateResult, SearchResult } from '../src/lib/contract';

export const hitFixture: SearchResult = {
  id: 'INC-1',
  text: 'db connection pool exhausted',
  score: 0.91,
  attribution: { dims: {}, terms: {}, confidence_margin: 0.1 },
};

export const analysisFixture: AnalyzeResult = {
  rca_draft: {
    root_cause_hypothesis: 'DB connection pool exhausted',
    evidence: ['INC-1: identical pool timeout'],
    severity_rationale: 'customer-facing outage',
    proposed_severity: 'high',
    proposed_assignee_team: 'platform',
    duplicate_check: [],
    knowledge_gaps: ['redis failover'],
    confidence_score: 0.82,
  },
  similar: [hitFixture],
  runbooks: [],
  flag_for_human: false,
};

export const duplicateFixture: DuplicateResult = {
  verdict: {
    is_duplicate: true,
    duplicate_of: 'INC-1',
    confidence: 0.91,
    rationale: 'same pool exhaustion, different wording',
    explanation: 'This looks like a duplicate of INC-1; linking them.',
    candidates: [],
  },
  similar: [hitFixture],
  flag_for_human: false,
};
