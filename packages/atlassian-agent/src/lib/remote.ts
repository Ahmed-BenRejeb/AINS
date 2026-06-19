/**
 * Forge Remote client — calls the `atlassian-remote` heavy-compute backend.
 *
 * Every call is authenticated with the shared `X-Sentinel-Secret` header and
 * carries the invoking user's `X-Account-Id` (atlassian-agent CLAUDE.md). Requests
 * are wrapped in {@link withBackoff} so a backend 429 is retried. The backend URL
 * comes from `FORGE_REMOTE_URL` and must also be allow-listed under
 * `permissions.external.fetch.backend` in `forge.yml`.
 */

import { fetch } from '@forge/api';

import { withBackoff } from './backoff';

const DEFAULT_REMOTE_URL = 'https://remote.ahmedxsaad.me';

/** Resolve the backend base URL from the environment, without a trailing slash. */
function remoteUrl(): string {
  return (process.env.FORGE_REMOTE_URL ?? DEFAULT_REMOTE_URL).replace(/\/+$/, '');
}

/**
 * POST a payload to an `atlassian-remote` endpoint and return its parsed JSON.
 *
 * @typeParam T - The expected response shape.
 * @param endpoint - Backend path segment (e.g. `"analyze"`, `"search"`).
 * @param payload - JSON-serialisable request body.
 * @param accountId - The invoking user's Atlassian account id (audit header).
 * @returns The parsed response body.
 * @throws If the backend responds with a non-2xx status (after retries).
 */
export async function callRemote<T>(
  endpoint: string,
  payload: Record<string, unknown>,
  accountId: string,
): Promise<T> {
  const response = await withBackoff(() =>
    fetch(`${remoteUrl()}/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Sentinel-Secret': process.env.FORGE_REMOTE_SECRET ?? '',
        'X-Account-Id': accountId,
      },
      body: JSON.stringify(payload),
    }),
  );
  if (!response.ok) {
    throw new Error(`atlassian-remote "${endpoint}" returned ${response.status}`);
  }
  return (await response.json()) as T;
}
