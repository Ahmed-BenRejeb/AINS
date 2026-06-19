import { searchRunbooks } from '../../src/actions/searchRunbooks';
import { searchSimilarIncidents } from '../../src/actions/searchSimilarIncidents';
import { callRemote } from '../../src/lib/remote';
import { hitFixture } from '../_fixtures';

jest.mock('../../src/lib/remote');

const callRemoteMock = callRemote as unknown as jest.Mock;
const context = { principal: { accountId: 'acc-7' } };

describe('search actions', () => {
  it('searchSimilarIncidents queries the incidents index', async () => {
    callRemoteMock.mockResolvedValueOnce({ results: [hitFixture] });

    const results = await searchSimilarIncidents({ query: 'db pool', limit: 3 }, context);

    expect(results).toEqual([hitFixture]);
    expect(callRemoteMock).toHaveBeenCalledWith(
      'search',
      { query: 'db pool', index: 'incidents', k: 3 },
      'acc-7',
    );
  });

  it('searchRunbooks queries the runbooks index with the default limit', async () => {
    callRemoteMock.mockResolvedValueOnce({ results: [] });

    await searchRunbooks({ query: 'redis failover' }, context);

    expect(callRemoteMock).toHaveBeenCalledWith(
      'search',
      { query: 'redis failover', index: 'runbooks', k: 5 },
      'acc-7',
    );
  });
});
