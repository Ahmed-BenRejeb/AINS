import api from '@forge/api';

import {
  addComment,
  createConfluencePage,
  createIncidentIssue,
  getIncident,
} from '../../src/lib/atlassian';
import { doc, paragraph, text } from '../../src/lib/adf';

const requestJira = api.asApp().requestJira as unknown as jest.Mock;
const requestConfluence = api.asApp().requestConfluence as unknown as jest.Mock;

function ok(body: unknown): unknown {
  return {
    ok: true,
    status: 200,
    headers: { get: (): string | null => null },
    json: async () => body,
  };
}

describe('atlassian client', () => {
  it('getIncident flattens summary + ADF description + status', async () => {
    requestJira.mockResolvedValueOnce(
      ok({
        key: 'AO-1',
        fields: {
          summary: 'DB outage',
          description: doc(paragraph(text('pool exhausted'))),
          status: { name: 'In Progress' },
        },
      }),
    );

    const incident = await getIncident('AO-1');

    expect(incident.key).toBe('AO-1');
    expect(incident.summary).toBe('DB outage');
    expect(incident.description).toContain('pool exhausted');
    expect(incident.status).toBe('In Progress');
  });

  it('addComment posts an ADF body to the comment endpoint', async () => {
    requestJira.mockResolvedValueOnce(ok({ id: 'c-1' }));

    const id = await addComment('AO-1', doc(paragraph(text('hi'))));

    expect(id).toBe('c-1');
    const [url, init] = requestJira.mock.calls[0] as [string, { body: string }];
    expect(url).toBe('/rest/api/3/issue/AO-1/comment');
    expect(JSON.parse(init.body).body.type).toBe('doc');
  });

  it('createIncidentIssue uses issue-type id 10013 and omits priority/labels', async () => {
    requestJira.mockResolvedValueOnce(ok({ key: 'AO-9' }));

    const key = await createIncidentIssue('Outage', doc(paragraph(text('d'))));

    expect(key).toBe('AO-9');
    const [, init] = requestJira.mock.calls[0] as [string, { body: string }];
    const fields = JSON.parse(init.body).fields;
    expect(fields.issuetype).toEqual({ id: '10013' });
    expect(fields.priority).toBeUndefined();
    expect(fields.labels).toBeUndefined();
  });

  it('createConfluencePage sends ADF (atlas_doc_format) addressed by space key', async () => {
    requestConfluence.mockResolvedValueOnce(ok({ id: 'p-1' }));

    const id = await createConfluencePage('SENT', 'PIR: AO-1', doc(paragraph(text('body'))));

    expect(id).toBe('p-1');
    const [url, init] = requestConfluence.mock.calls[0] as [string, { body: string }];
    expect(url).toBe('/wiki/rest/api/content');
    const payload = JSON.parse(init.body);
    expect(payload.space.key).toBe('SENT');
    expect(payload.body.atlas_doc_format.representation).toBe('atlas_doc_format');
  });
});
