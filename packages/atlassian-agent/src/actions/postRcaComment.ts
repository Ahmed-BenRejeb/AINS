/** Rovo action: draft an RCA via the backend and post it as an ADF comment. */

import { rcaToAdf } from '../lib/adf';
import { addComment } from '../lib/atlassian';
import type { AnalyzeResult } from '../lib/contract';
import { accountIdOf, type ActionContext } from '../lib/context';
import { callRemote } from '../lib/remote';

/** Input for the {@link postRcaComment} action. */
export interface PostRcaCommentInput {
  issueKey: string;
}

/** Result of the {@link postRcaComment} action. */
export interface PostRcaCommentResult {
  commentId: string;
  proposedSeverity: string;
  flagForHuman: boolean;
}

/**
 * Generate a root-cause-analysis draft for an incident and post it as a comment.
 *
 * Calls the backend `/analyze` (which retrieves similar incidents + runbooks and
 * drafts the RCA), renders it to ADF, and adds it as a Jira comment.
 *
 * @param payload - The action input containing the issue key.
 * @param context - The Forge invocation context (supplies the account id).
 * @returns The created comment id, the proposed severity, and the review flag.
 */
export async function postRcaComment(
  payload: PostRcaCommentInput,
  context: ActionContext,
): Promise<PostRcaCommentResult> {
  const accountId = accountIdOf(context);
  const analysis = await callRemote<AnalyzeResult>(
    'analyze',
    { incident_key: payload.issueKey, requested_by: accountId },
    accountId,
  );
  const commentId = await addComment(payload.issueKey, rcaToAdf(analysis));
  return {
    commentId,
    proposedSeverity: analysis.rca_draft.proposed_severity,
    flagForHuman: analysis.flag_for_human,
  };
}
