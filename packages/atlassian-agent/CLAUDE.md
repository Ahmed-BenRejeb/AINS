# atlassian-agent / CLAUDE.md

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
├── forge.yml              Forge app manifest
├── package.json
├── tsconfig.json          strict TypeScript
├── src/
│   ├── index.ts
│   ├── actions/
│   │   ├── fetchIncident.ts
│   │   ├── searchSimilarIncidents.ts
│   │   ├── searchRunbooks.ts
│   │   ├── postRcaComment.ts
│   │   ├── draftPirPage.ts
│   │   └── flagKnowledgeGap.ts
│   └── lib/
│       ├── atlassian.ts   @forge/api wrappers
│       ├── remote.ts      Forge Remote fetch helper
│       └── backoff.ts     exponential backoff for 429
└── tests/
    └── __mocks__/@forge/api.ts
```

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

export async function callRemote<T>(
  endpoint: string,
  payload: Record<string, unknown>,
  context: { principal: { accountId: string } }
): Promise<T> {
  const response = await fetch(
    `${process.env.FORGE_REMOTE_URL}/${endpoint}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Sentinel-Secret': process.env.FORGE_REMOTE_SECRET!,
        'X-Account-Id': context.principal.accountId,
      },
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) throw new Error(`Remote: ${response.status}`);
  return response.json() as Promise<T>;
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