# atlassian-agent / CLAUDE.md

> **✅ PROJECT COMPLETE — FINAL VERSION.** UC3 Forge agent done & deployed (v2.2.0): Rovo agent + 7 actions, installed on Jira **and** Confluence at ahmedains.atlassian.net.
>
> Read the root `CLAUDE.md` first, especially Section 0 (deployed infra).
> This package deploys to Atlassian's Forge infrastructure via `make deploy-forge`.

## What This Package Does

**UC3: The Forge Rovo Agent.**
Defines the Rovo Agent manifest and its Actions. Handles Atlassian-native work:
fetching JSM/Jira/Confluence data, posting comments, creating pages.
Heavy compute is delegated to `atlassian-remote` via Forge Remote.

## Deployed Atlassian Environment

```
Site:              https://ahmedains.atlassian.net
JSM project:       AO (key)
Service desk ID:   1
Incident type ID:  10013  ← always use ID, never {"name": "Incident"}
Confluence space:  SENT
Forge Remote URL:  https://remote.ahmedxsaad.me
```

## Key Files

```
atlassian-agent/
├── manifest.yml           Forge manifest: 1 rovo:agent + 7 action + 7 function modules
├── package.json
├── tsconfig.json          strict TypeScript ("strict": true, noUncheckedIndexedAccess)
├── jest.config.js         ts-jest; roots=tests/ so the @forge/api manual mock auto-applies
├── .eslintrc.cjs / .prettierrc.json
├── src/
│   ├── index.ts           re-exports the 7 handlers (handler: index.<fn>)
│   ├── actions/
│   │   ├── fetchIncident.ts            (Atlassian-native read)
│   │   ├── searchSimilarIncidents.ts   (→ remote /search, index=incidents)
│   │   ├── searchRunbooks.ts           (→ remote /search, index=runbooks)
│   │   ├── postRcaComment.ts           (→ remote /analyze → ADF comment)
│   │   ├── resolveDuplicate.ts         (→ remote /duplicates → link issues + ADF comment)
│   │   ├── draftPirPage.ts             (→ remote /analyze → Confluence ADF page)
│   │   └── flagKnowledgeGap.ts         (Atlassian-native AO issue, id 10013)
│   └── lib/
│       ├── atlassian.ts   @forge/api wrappers (Jira + Confluence; getIncident/addComment/linkIssues/...)
│       ├── remote.ts      Forge Remote client (callRemote — secret + account-id headers)
│       ├── backoff.ts     withBackoff — exponential backoff for 429
│       ├── adf.ts         ADF builders + renderers (rcaToAdf / pirToAdf / adfToText)
│       ├── context.ts     accountIdOf(context) — resolve the invoking account id
│       └── contract.ts    types mirroring trace_core/schema.ts (+ AnalyzeResult envelope)
└── tests/
    ├── lib/*.test.ts       backoff / remote / atlassian / adf
    ├── actions/*.test.ts   one per action (lib layer mocked)
    ├── _fixtures.ts        shared AnalyzeResult / SearchResult fixtures
    └── __mocks__/@forge/api.ts   manual mock (asApp().requestJira/requestConfluence, fetch, route)
```

> Not every action calls the backend: `fetch-incident` and `flag-knowledge-gap` are
> Atlassian-native; the search / RCA / PIR / duplicate actions delegate heavy compute to
> `atlassian-remote`. All Jira/Confluence write bodies are ADF (Confluence uses the
> `atlas_doc_format` representation so a space **key** can be used directly).
>
> `resolve-duplicate` is the only action that writes the Jira **link graph**: when the
> backend `/duplicates` verdict is a confident duplicate (not flagged for human review)
> it calls `linkIssues` (`POST /rest/api/3/issueLink`, type name from
> `ATLASSIAN_DUPLICATE_LINK_TYPE`, default `Duplicate`) then comments; otherwise it only
> posts the surfaced candidates for a human (graceful degradation).

## Critical: Issue Type ID (not name)

```typescript
// CORRECT — JSM AO project requires ID
const issue = {
  fields: {
    project: { key: "AO" },
    summary: incidentSummary,
    issuetype: { id: "10013" },   // [System] Incident
    // do NOT include priority or labels — AO rejects them
  }
};

// WRONG — returns 400 Bad Request
const issue = {
  fields: { issuetype: { name: "Incident" } }
};
```

## Forge Remote Call Pattern

```typescript
import { fetch } from '@forge/api';
import { withBackoff } from './backoff';

// lib/remote.ts — actions pass accountIdOf(context); withBackoff retries on 429.
export async function callRemote<T>(
  endpoint: string,
  payload: Record<string, unknown>,
  accountId: string,
): Promise<T> {
  const response = await withBackoff(() =>
    fetch(`${remoteUrl()}/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Sentinel-Secret': process.env.FORGE_REMOTE_SECRET ?? '',
        'X-Account-Id': accountId,
      },
      body: JSON.stringify(payload),
    }),
  );
  if (!response.ok) throw new Error(`atlassian-remote "${endpoint}" returned ${response.status}`);
  return (await response.json()) as T;
}
```

## Atlassian Document Format (ADF) — Required for all Jira/Confluence content

```typescript
// All body content must be ADF — NOT plain strings or markdown
const commentBody = {
  type: "doc", version: 1,
  content: [{
    type: "paragraph",
    content: [{ type: "text", text: "Your content here" }]
  }]
};
```

## Commands

```bash
cd packages/atlassian-agent
pnpm install
pnpm test
pnpm typecheck

# Deploy to Atlassian dev site
forge deploy --environment development
forge install --environment development --site https://ahmedains.atlassian.net
# Or via Makefile:
make deploy-forge
```