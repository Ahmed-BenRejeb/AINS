import { flagKnowledgeGap } from '../../src/actions/flagKnowledgeGap';
import { createIncidentIssue } from '../../src/lib/atlassian';

jest.mock('../../src/lib/atlassian');

const createIncidentIssueMock = createIncidentIssue as unknown as jest.Mock;

describe('flagKnowledgeGap', () => {
  it('creates a tracking issue describing the missing runbook topic', async () => {
    createIncidentIssueMock.mockResolvedValueOnce('AO-42');

    const result = await flagKnowledgeGap({ topic: 'redis failover', issueKey: 'AO-1' });

    const [summary, body] = createIncidentIssueMock.mock.calls[0] as [string, { type: string }];
    expect(summary).toContain('redis failover');
    expect(body.type).toBe('doc');
    expect(result).toEqual({ issueKey: 'AO-42' });
  });
});
