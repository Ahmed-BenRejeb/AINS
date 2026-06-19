/** Rovo action: draft a post-incident-review Confluence page from the backend RCA. */

import { pirToAdf } from '../lib/adf';
import { createConfluencePage } from '../lib/atlassian';
import type { AnalyzeResult } from '../lib/contract';
import { accountIdOf, type ActionContext } from '../lib/context';
import { callRemote } from '../lib/remote';

const DEFAULT_SPACE_KEY = 'SENT';

/** Input for the {@link draftPirPage} action. */
export interface DraftPirPageInput {
  issueKey: string;
  spaceKey?: string;
}

/** Result of the {@link draftPirPage} action. */
export interface DraftPirPageResult {
  pageId: string;
  spaceKey: string;
  title: string;
}

/**
 * Draft a post-incident-review Confluence page for an incident.
 *
 * Calls the backend `/analyze` for the RCA, renders it to an ADF page body, and
 * creates the page in the target space (default `SENT`).
 *
 * @param payload - The issue key and optional Confluence space key.
 * @param context - The Forge invocation context (supplies the account id).
 * @returns The created page id, the space it was created in, and its title.
 */
export async function draftPirPage(
  payload: DraftPirPageInput,
  context: ActionContext,
): Promise<DraftPirPageResult> {
  const accountId = accountIdOf(context);
  const analysis = await callRemote<AnalyzeResult>(
    'analyze',
    { incident_key: payload.issueKey, requested_by: accountId },
    accountId,
  );
  const spaceKey = payload.spaceKey ?? DEFAULT_SPACE_KEY;
  const title = `Post-Incident Review: ${payload.issueKey}`;
  const pageId = await createConfluencePage(spaceKey, title, pirToAdf(payload.issueKey, analysis));
  return { pageId, spaceKey, title };
}
