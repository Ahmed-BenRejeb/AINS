import { fetchIncident } from '../../src/actions/fetchIncident';
import { getIncident } from '../../src/lib/atlassian';

jest.mock('../../src/lib/atlassian');

const getIncidentMock = getIncident as unknown as jest.Mock;

describe('fetchIncident', () => {
  it('returns the flattened incident summary', async () => {
    const incident = { key: 'AO-1', summary: 's', description: 'd', status: 'Open' };
    getIncidentMock.mockResolvedValueOnce(incident);

    const result = await fetchIncident({ issueKey: 'AO-1' });

    expect(result).toEqual(incident);
    expect(getIncidentMock).toHaveBeenCalledWith('AO-1');
  });
});
