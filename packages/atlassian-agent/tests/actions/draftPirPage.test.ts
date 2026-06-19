import { draftPirPage } from '../../src/actions/draftPirPage';
import { createConfluencePage } from '../../src/lib/atlassian';
import { callRemote } from '../../src/lib/remote';
import { analysisFixture } from '../_fixtures';

jest.mock('../../src/lib/remote');
jest.mock('../../src/lib/atlassian');

const callRemoteMock = callRemote as unknown as jest.Mock;
const createConfluencePageMock = createConfluencePage as unknown as jest.Mock;

describe('draftPirPage', () => {
  it('analyses via the backend then creates a PIR page in the default space', async () => {
    callRemoteMock.mockResolvedValueOnce(analysisFixture);
    createConfluencePageMock.mockResolvedValueOnce('page-1');

    const result = await draftPirPage({ issueKey: 'AO-1' }, { principal: { accountId: 'acc' } });

    expect(callRemoteMock).toHaveBeenCalledWith(
      'analyze',
      { incident_key: 'AO-1', requested_by: 'acc' },
      'acc',
    );
    const [spaceKey, title, body] = createConfluencePageMock.mock.calls[0] as [
      string,
      string,
      { type: string },
    ];
    expect(spaceKey).toBe('SENT');
    expect(title).toContain('AO-1');
    expect(body.type).toBe('doc');
    expect(result).toEqual({ pageId: 'page-1', spaceKey: 'SENT', title });
  });
});
