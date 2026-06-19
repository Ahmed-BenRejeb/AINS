import { withBackoff, type ResponseLike } from '../../src/lib/backoff';

function response(status: number, retryAfter: string | null = null): ResponseLike {
  return {
    status,
    headers: { get: (name: string): string | null => (name === 'Retry-After' ? retryAfter : null) },
  };
}

describe('withBackoff', () => {
  it('returns immediately on a non-429 response', async () => {
    const attempt = jest.fn().mockResolvedValue(response(200));

    const result = await withBackoff(attempt, { baseMs: 1, maxMs: 2 });

    expect(result.status).toBe(200);
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it('retries on 429 then returns the success response', async () => {
    const attempt = jest
      .fn()
      .mockResolvedValueOnce(response(429, '0'))
      .mockResolvedValueOnce(response(200));

    const result = await withBackoff(attempt, { baseMs: 1, maxMs: 2 });

    expect(result.status).toBe(200);
    expect(attempt).toHaveBeenCalledTimes(2);
  });

  it('gives up after maxRetries and returns the last 429', async () => {
    const attempt = jest.fn().mockResolvedValue(response(429));

    const result = await withBackoff(attempt, { maxRetries: 3, baseMs: 1, maxMs: 2 });

    expect(result.status).toBe(429);
    expect(attempt).toHaveBeenCalledTimes(4); // initial call + 3 retries
  });
});
