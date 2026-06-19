/** Rovo action: find runbooks relevant to some incident text (via the backend). */

import type { SearchResponse, SearchResult } from '../lib/contract';
import { accountIdOf, type ActionContext } from '../lib/context';
import { callRemote } from '../lib/remote';

const DEFAULT_LIMIT = 5;

/** Input for the {@link searchRunbooks} action. */
export interface SearchRunbooksInput {
  query: string;
  limit?: number;
}

/**
 * Search the `runbooks` collection for runbooks relevant to the query text.
 *
 * @param payload - The query text and optional result cap.
 * @param context - The Forge invocation context (supplies the account id).
 * @returns The ranked relevant runbooks (each with attribution).
 */
export async function searchRunbooks(
  payload: SearchRunbooksInput,
  context: ActionContext,
): Promise<SearchResult[]> {
  const response = await callRemote<SearchResponse>(
    'search',
    { query: payload.query, index: 'runbooks', k: payload.limit ?? DEFAULT_LIMIT },
    accountIdOf(context),
  );
  return response.results;
}
