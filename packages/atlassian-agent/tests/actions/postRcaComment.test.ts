import { postRcaComment } from '../../src/actions/postRcaComment';
import { addComment } from '../../src/lib/atlassian';
import { callRemote } from '../../src/lib/remote';
import { analysisFixture } from '../_fixtures';

jest.mock('../../src/lib/remote');
jest.mock('../../src/lib/atlassian');

const callRemoteMock = callRemote as unknown as jest.Mock;
const addCommentMock = addComment as unknown as jest.Mock;

describe('postRcaComment', () => {
  it('analyses via the backend then posts an ADF comment', async () => {
    callRemoteMock.mockResolvedValueOnce(analysisFixture);
    addCommentMock.mockResolvedValueOnce('comment-1');

    const result = await postRcaComment(
      { issueKey: 'AO-1' },
      { principal: { accountId: 'acc-9' } },
    );

    expect(callRemoteMock).toHaveBeenCalledWith(
      'analyze',
      { incident_key: 'AO-1', requested_by: 'acc-9' },
      'acc-9',
    );
    const [issueKey, body] = addCommentMock.mock.calls[0] as [string, { type: string }];
    expect(issueKey).toBe('AO-1');
    expect(body.type).toBe('doc'); // posted body is an ADF document
    expect(result).toEqual({
      commentId: 'comment-1',
      proposedSeverity: 'high',
      flagForHuman: false,
    });
  });
});
