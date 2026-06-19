/** Rovo action: fetch a Jira incident's details (Atlassian-native, no backend). */

import { getIncident, type IncidentSummary } from '../lib/atlassian';

/** Input for the {@link fetchIncident} action. */
export interface FetchIncidentInput {
  issueKey: string;
}

/**
 * Fetch an incident's summary, description, and status by issue key.
 *
 * @param payload - The action input containing the issue key.
 * @returns The flattened incident summary.
 */
export async function fetchIncident(payload: FetchIncidentInput): Promise<IncidentSummary> {
  return getIncident(payload.issueKey);
}
