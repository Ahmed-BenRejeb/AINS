import { fetch } from '@forge/api';

import { callRemote } from '../../src/lib/remote';

const fetchMock = fetch as unknown as jest.Mock;

interface FakeInit {
  headers: Record<string, string>;
  body: string;
}

function jsonResponse(body: unknown, ok = true, status = 200): unknown {
  return { ok, status, headers: { get: (): string | null => null }, json: async () => body };
}

describe('callRemote', () => {
  beforeEach(() => {
    process.env.FORGE_REMOTE_URL = 'https://remote.example';
    process.env.FORGE_REMOTE_SECRET = 'shhh';
  });

  it('posts the payload with auth headers and returns parsed JSON', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ results: [] }));

    const result = await callRemote('search', { query: 'db' }, 'acc-1');

    expect(result).toEqual({ results: [] });
    const [url, init] = fetchMock.mock.calls[0] as [string, FakeInit];
    expect(url).toBe('https://remote.example/search');
    expect(init.headers['X-Sentinel-Secret']).toBe('shhh');
    expect(init.headers['X-Account-Id']).toBe('acc-1');
    expect(JSON.parse(init.body)).toEqual({ query: 'db' });
  });

  it('throws when the backend returns a non-2xx status', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, false, 500));

    await expect(callRemote('analyze', {}, 'acc-1')).rejects.toThrow('500');
  });
});
