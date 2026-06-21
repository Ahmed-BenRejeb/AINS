/** Rovo action: detect a semantic duplicate and, when confident, link + comment. */

import { duplicateToAdf } from '../lib/adf';
import { addComment, linkIssues } from '../lib/atlassian';
import type { DuplicateResult } from '../lib/contract';
import { accountIdOf, type ActionContext } from '../lib/context';
import { callRemote } from '../lib/remote';

/** Input for the {@link resolveDuplicate} action. */
export interface ResolveDuplicateInput {
  issueKey: string;
}

/** Result of the {@link resolveDuplicate} action. */
export interface ResolveDuplicateResult {
  commentId: string;
  isDuplicate: boolean;
  duplicateOf: string | null;
  linked: boolean;
  flagForHuman: boolean;
}

/**
 * Check whether an incident is a semantic duplicate of a past one and act on it.
 *
 * Calls the backend `/duplicates` (which retrieves similar incidents and judges
 * the match). When the verdict is a confident duplicate (`is_duplicate` and not
 * flagged for human review), it links the two issues with the duplicate link type
 * and posts the polite explanation. Otherwise it posts the surfaced candidates for
 * a human to review and does not mutate the link graph (graceful degradation).
 *
 * @param payload - The action input containing the issue key.
 * @param context - The Forge invocation context (supplies the account id).
 * @returns The created comment id, the verdict, whether a link was created, and the
 *   review flag.
 */
export async function resolveDuplicate(
  payload: ResolveDuplicateInput,
  context: ActionContext,
): Promise<ResolveDuplicateResult> {
  const accountId = accountIdOf(context);
  const result = await callRemote<DuplicateResult>(
    'duplicates',
    { incident_key: payload.issueKey, requested_by: accountId },
    accountId,
  );
  const verdict = result.verdict;
  let linked = false;
  if (verdict.is_duplicate && !result.flag_for_human && verdict.duplicate_of) {
    await linkIssues(payload.issueKey, verdict.duplicate_of);
    linked = true;
  }
  const commentId = await addComment(payload.issueKey, duplicateToAdf(result));
  return {
    commentId,
    isDuplicate: verdict.is_duplicate,
    duplicateOf: verdict.duplicate_of,
    linked,
    flagForHuman: result.flag_for_human,
  };
}
