/** Rovo action: record a missing-runbook knowledge gap as a tracked Jira issue. */

import { gapToAdf } from '../lib/adf';
import { createIncidentIssue } from '../lib/atlassian';

/** Input for the {@link flagKnowledgeGap} action. */
export interface FlagKnowledgeGapInput {
  topic: string;
  issueKey?: string;
}

/** Result of the {@link flagKnowledgeGap} action. */
export interface FlagKnowledgeGapResult {
  issueKey: string;
}

/**
 * Record a knowledge gap (a topic with no runbook) as an AO tracking issue.
 *
 * Atlassian-native: creates an Incident-type issue (id 10013, no priority/labels)
 * describing the gap so a runbook can be authored.
 *
 * @param payload - The missing topic and the incident that surfaced it (if any).
 * @returns The created tracking issue's key.
 */
export async function flagKnowledgeGap(
  payload: FlagKnowledgeGapInput,
): Promise<FlagKnowledgeGapResult> {
  const summary = `Knowledge gap: no runbook for "${payload.topic}"`;
  const issueKey = await createIncidentIssue(summary, gapToAdf(payload.topic, payload.issueKey));
  return { issueKey };
}
