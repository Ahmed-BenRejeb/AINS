/** Rovo action: find past incidents similar to some text (via the backend). */

import type { SearchResponse, SearchResult } from '../lib/contract';
import { accountIdOf, type ActionContext } from '../lib/context';
import { callRemote } from '../lib/remote';

const DEFAULT_LIMIT = 5;

/** Input for the {@link searchSimilarIncidents} action. */
export interface SearchSimilarIncidentsInput {
  query: string;
  limit?: number;
}

/**
 * Search the `incidents` collection for semantically similar past incidents.
 *
 * @param payload - The query text and optional result cap.
 * @param context - The Forge invocation context (supplies the account id).
 * @returns The ranked similar incidents (each with attribution).
 */
export async function searchSimilarIncidents(
  payload: SearchSimilarIncidentsInput,
  context: ActionContext,
): Promise<SearchResult[]> {
  const response = await callRemote<SearchResponse>(
    'search',
    { query: payload.query, index: 'incidents', k: payload.limit ?? DEFAULT_LIMIT },
    accountIdOf(context),
  );
  return response.results;
}
