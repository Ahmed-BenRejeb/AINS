/**
 * Atlassian-native operations via the Forge `@forge/api` product clients.
 *
 * Jira/Confluence reads and writes that belong inside the Forge sandbox. Issue
 * creation follows the AO project's hard rules (root CLAUDE.md §10): issue-type
 * **id** `10013` (never the name), and no `priority` / `labels`. All write bodies
 * are ADF (see {@link module:lib/adf}). Calls are wrapped in {@link withBackoff}
 * to absorb Atlassian's 429 rate limiting.
 */

import api, { route } from '@forge/api';

import type { AdfDoc } from './adf';
import { adfToText } from './adf';
import { withBackoff } from './backoff';

const INCIDENT_ISSUE_TYPE_ID = '10013';

/** The AO project key (overridable via env, defaults to `AO`). */
function jiraProjectKey(): string {
  return process.env.ATLASSIAN_JIRA_PROJECT_KEY ?? 'AO';
}

/** The Jira issue-link type used for duplicates (overridable; default `Duplicate`). */
function duplicateLinkType(): string {
  return process.env.ATLASSIAN_DUPLICATE_LINK_TYPE ?? 'Duplicate';
}

/** A flattened incident summary returned by {@link getIncident}. */
export interface IncidentSummary {
  key: string;
  summary: string;
  description: string;
  status: string;
}

interface JiraIssueResponse {
  key: string;
  fields?: {
    summary?: string;
    description?: unknown;
    status?: { name?: string };
  };
}

/**
 * Fetch a Jira incident and flatten its key fields to plain text.
 *
 * @param issueKey - The Jira issue key (e.g. `"AO-123"`).
 * @returns The incident's key, summary, flattened description, and status name.
 * @throws If Jira responds with a non-2xx status.
 */
export async function getIncident(issueKey: string): Promise<IncidentSummary> {
  const response = await withBackoff(() =>
    api.asApp().requestJira(route`/rest/api/3/issue/${issueKey}?fields=summary,description,status`),
  );
  if (!response.ok) {
    throw new Error(`getIncident "${issueKey}" returned ${response.status}`);
  }
  const issue = (await response.json()) as JiraIssueResponse;
  return {
    key: issue.key,
    summary: issue.fields?.summary ?? '',
    description: adfToText(issue.fields?.description),
    status: issue.fields?.status?.name ?? 'unknown',
  };
}

/**
 * Add an ADF comment to a Jira issue.
 *
 * @param issueKey - The issue to comment on.
 * @param body - The comment body as an ADF document.
 * @returns The created comment's id.
 * @throws If Jira responds with a non-2xx status.
 */
export async function addComment(issueKey: string, body: AdfDoc): Promise<string> {
  const response = await withBackoff(() =>
    api.asApp().requestJira(route`/rest/api/3/issue/${issueKey}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ body }),
    }),
  );
  if (!response.ok) {
    throw new Error(`addComment "${issueKey}" returned ${response.status}`);
  }
  const created = (await response.json()) as { id: string };
  return created.id;
}

/**
 * Link two Jira issues with the configured duplicate link type.
 *
 * The link-type **name** must exist on the site; "Duplicate" is a Jira default but
 * is not guaranteed, so it is configurable via `ATLASSIAN_DUPLICATE_LINK_TYPE`
 * (analogous to the issue-type-ID rule — root CLAUDE.md §10).
 *
 * @param inwardKey - The new (duplicate) incident, e.g. `"AO-200"`.
 * @param outwardKey - The existing (canonical) incident it duplicates, e.g. `"AO-12"`.
 * @returns Nothing on success.
 * @throws If Jira responds with a non-2xx status.
 */
export async function linkIssues(inwardKey: string, outwardKey: string): Promise<void> {
  const response = await withBackoff(() =>
    api.asApp().requestJira(route`/rest/api/3/issueLink`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        type: { name: duplicateLinkType() },
        inwardIssue: { key: inwardKey },
        outwardIssue: { key: outwardKey },
      }),
    }),
  );
  if (!response.ok) {
    throw new Error(`linkIssues "${inwardKey}" -> "${outwardKey}" returned ${response.status}`);
  }
}

/**
 * Create an Incident in the AO project (issue-type id 10013, no priority/labels).
 *
 * @param summary - The issue summary line.
 * @param description - The issue description as an ADF document.
 * @returns The created issue key (e.g. `"AO-456"`).
 * @throws If Jira responds with a non-2xx status.
 */
export async function createIncidentIssue(summary: string, description: AdfDoc): Promise<string> {
  const response = await withBackoff(() =>
    api.asApp().requestJira(route`/rest/api/3/issue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        fields: {
          project: { key: jiraProjectKey() },
          summary,
          // Use the issue-type ID — the name "[System] Incident" is rejected, and
          // the AO project rejects priority/labels, so neither is sent.
          issuetype: { id: INCIDENT_ISSUE_TYPE_ID },
          description,
        },
      }),
    }),
  );
  if (!response.ok) {
    throw new Error(`createIncidentIssue returned ${response.status}`);
  }
  const created = (await response.json()) as { key: string };
  return created.key;
}

/**
 * Create a Confluence page from an ADF document, addressed by space key.
 *
 * Uses the v1 content API with the `atlas_doc_format` representation so the body
 * stays ADF rather than storage-format XHTML.
 *
 * @param spaceKey - The Confluence space key (e.g. `"SENT"`).
 * @param title - The page title (must be unique within the space).
 * @param body - The page body as an ADF document.
 * @returns The created page id.
 * @throws If Confluence responds with a non-2xx status.
 */
export async function createConfluencePage(
  spaceKey: string,
  title: string,
  body: AdfDoc,
): Promise<string> {
  const response = await withBackoff(() =>
    api.asApp().requestConfluence(route`/wiki/rest/api/content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        type: 'page',
        title,
        space: { key: spaceKey },
        body: {
          atlas_doc_format: { value: JSON.stringify(body), representation: 'atlas_doc_format' },
        },
      }),
    }),
  );
  if (!response.ok) {
    throw new Error(`createConfluencePage returned ${response.status}`);
  }
  const created = (await response.json()) as { id: string };
  return created.id;
}
