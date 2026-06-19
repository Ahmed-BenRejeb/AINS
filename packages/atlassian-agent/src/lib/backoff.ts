/** Exponential backoff for Atlassian / remote rate limits (HTTP 429). */

/** The minimal response surface backoff needs (satisfied by node-fetch Response). */
export interface ResponseLike {
  readonly status: number;
  readonly headers: { get(name: string): string | null };
}

/** Tunables for {@link withBackoff}. */
export interface BackoffOptions {
  readonly maxRetries?: number;
  readonly baseMs?: number;
  readonly maxMs?: number;
}

const DEFAULTS = { maxRetries: 5, baseMs: 500, maxMs: 8000 } as const;

/**
 * Sleep for `ms` milliseconds. Isolated so tests can stub it without real time.
 *
 * @param ms - Milliseconds to wait.
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Compute the delay before the next retry: honour `Retry-After`, else exponential.
 *
 * @param response - The 429 response (may carry a `Retry-After` header).
 * @param attempt - 0-based retry attempt index.
 * @param options - Resolved backoff tunables.
 * @returns Delay in milliseconds, capped at `maxMs`.
 */
function retryDelayMs(
  response: ResponseLike,
  attempt: number,
  options: Required<BackoffOptions>,
): number {
  const retryAfter = Number(response.headers.get('Retry-After'));
  if (Number.isFinite(retryAfter) && retryAfter > 0) {
    return Math.min(retryAfter * 1000, options.maxMs);
  }
  return Math.min(options.baseMs * 2 ** attempt, options.maxMs);
}

/**
 * Run `attempt` and retry while it returns HTTP 429, backing off exponentially.
 *
 * @param attempt - A function that performs one request and resolves a response.
 * @param options - Optional backoff tunables.
 * @returns The first non-429 response, or the last 429 once retries are exhausted.
 */
export async function withBackoff<T extends ResponseLike>(
  attempt: () => Promise<T>,
  options: BackoffOptions = {},
): Promise<T> {
  const resolved: Required<BackoffOptions> = { ...DEFAULTS, ...options };
  let response = await attempt();
  for (let i = 0; i < resolved.maxRetries && response.status === 429; i += 1) {
    await sleep(retryDelayMs(response, i, resolved));
    response = await attempt();
  }
  return response;
}
