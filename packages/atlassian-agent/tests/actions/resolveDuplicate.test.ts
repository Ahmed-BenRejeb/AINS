import { resolveDuplicate } from '../../src/actions/resolveDuplicate';
import { addComment, linkIssues } from '../../src/lib/atlassian';
import { callRemote } from '../../src/lib/remote';
import { duplicateFixture } from '../_fixtures';
import type { DuplicateResult } from '../../src/lib/contract';

jest.mock('../../src/lib/remote');
jest.mock('../../src/lib/atlassian');

const callRemoteMock = callRemote as unknown as jest.Mock;
const addCommentMock = addComment as unknown as jest.Mock;
const linkIssuesMock = linkIssues as unknown as jest.Mock;

describe('resolveDuplicate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('links the issues and comments when confident', async () => {
    callRemoteMock.mockResolvedValueOnce(duplicateFixture);
    linkIssuesMock.mockResolvedValueOnce(undefined);
    addCommentMock.mockResolvedValueOnce('comment-1');

    const result = await resolveDuplicate(
      { issueKey: 'AO-1' },
      { principal: { accountId: 'acc-9' } },
    );

    expect(callRemoteMock).toHaveBeenCalledWith(
      'duplicates',
      { incident_key: 'AO-1', requested_by: 'acc-9' },
      'acc-9',
    );
    expect(linkIssuesMock).toHaveBeenCalledWith('AO-1', 'INC-1');
    const [issueKey, body] = addCommentMock.mock.calls[0] as [string, { type: string }];
    expect(issueKey).toBe('AO-1');
    expect(body.type).toBe('doc'); // posted body is an ADF document
    expect(result).toEqual({
      commentId: 'comment-1',
      isDuplicate: true,
      duplicateOf: 'INC-1',
      linked: true,
      flagForHuman: false,
    });
  });

  it('surfaces candidates without linking when flagged for human review', async () => {
    const flagged: DuplicateResult = {
      ...duplicateFixture,
      flag_for_human: true,
      verdict: { ...duplicateFixture.verdict, confidence: 0.5 },
    };
    callRemoteMock.mockResolvedValueOnce(flagged);
    addCommentMock.mockResolvedValueOnce('comment-2');

    const result = await resolveDuplicate(
      { issueKey: 'AO-1' },
      { principal: { accountId: 'acc-9' } },
    );

    expect(linkIssuesMock).not.toHaveBeenCalled();
    expect(addCommentMock).toHaveBeenCalledTimes(1); // comment still posted
    expect(result.linked).toBe(false);
    expect(result.flagForHuman).toBe(true);
  });
});
