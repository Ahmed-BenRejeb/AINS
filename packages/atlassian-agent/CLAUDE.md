# atlassian-agent / CLAUDE.md

> Read the root `CLAUDE.md` first. This file adds package-specific context.

## What This Package Does

**UC3: The Forge Rovo Agent.** A native Atlassian app built with Forge (TypeScript) that defines a Rovo AI agent with custom Actions. It handles the lightweight Atlassian-native work: fetching incident data, posting comments, creating pages. All heavy compute (embeddings, LLM, vector search) is delegated to `atlassian-remote` via Forge Remote.

## Key Files

```
atlassian-agent/
├── forge.yml               ← Forge app manifest (rovo:agent, rovo:action modules)
├── package.json
├── tsconfig.json           ← strict TypeScript — "strict": true required
├── src/
│   ├── index.ts            ← entry point, exports all action handlers
│   ├── actions/
│   │   ├── fetchIncident.ts        ← GET incident from JSM, normalize to our schema
│   │   ├── searchSimilarIncidents.ts ← call atlassian-remote /search endpoint
│   │   ├── searchRunbooks.ts       ← call atlassian-remote /search endpoint
│   │   ├── postRcaComment.ts       ← POST structured RCA comment to Jira
│   │   ├── draftPirPage.ts         ← CREATE Confluence PIR page from RCA
│   │   └── flagKnowledgeGap.ts     ← CREATE Confluence stub page for knowledge gap
│   └── lib/
│       ├── atlassian.ts    ← @forge/api wrappers for Jira + Confluence + JSM calls
│       ├── remote.ts       ← Forge Remote fetch helper (calls atlassian-remote backend)
│       └── backoff.ts      ← exponential backoff for Atlassian API 429 responses
└── tests/
    ├── fetchIncident.test.ts
    ├── postRcaComment.test.ts
    └── __mocks__/
        └── @forge/api.ts   ← mock for Forge API in tests
```

## How Forge Works (Quick Reference)

Forge is Atlassian's serverless platform. Apps run in a V8 sandbox on Atlassian's AWS infrastructure.

```yaml
# forge.yml — the manifest defines what the app exposes
modules:
  rovo:agent:         # defines the AI agent visible in Atlassian
    - key: incident-rca-agent
      prompt: ...     # system prompt for the agent
      actions:        # tools the agent can call
        - fetch-incident
        - search-similar-incidents

  rovo:action:        # each action is a tool definition
    - key: fetch-incident
      name: Fetch Incident
      function: fetchIncidentFn  # the TypeScript function that runs it
      inputs:
        incident_key:
          title: Incident Key
          type: string
          required: true
```

## Critical Rules for This Package

- **Forge sandbox has strict compute limits.** Do NOT make large LLM calls or run embeddings inside Forge functions. All heavy work goes through `remote.ts` → `atlassian-remote` backend.
- **Always use `asUser()` for Atlassian API calls.** This ensures the action runs with the permission of the user who invoked it, not the app's system permissions.
- **Always pass `principal.accountId` to the remote endpoint.** The remote backend uses this for audit logging.
- **No `any` type anywhere.** TypeScript strict mode is enforced. ESLint will fail the build if `any` appears without a `// eslint-disable-next-line` comment with justification.
- **Test with Forge mocks, not live calls.** The `__mocks__/@forge/api.ts` mock simulates Forge's API client. Use it in all tests.

## Forge Remote Call Pattern

```typescript
// lib/remote.ts — always use this, never raw fetch
import { fetch } from '@forge/api';

export async function callRemote<T>(
  endpoint: string,
  payload: Record<string, unknown>,
  context: { principal: { accountId: string } }
): Promise<T> {
  const response = await fetch(`${process.env.FORGE_REMOTE_URL}/${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Sentinel-Secret': process.env.FORGE_REMOTE_SECRET!,
      'X-Account-Id': context.principal.accountId,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Remote call failed: ${response.status} ${await response.text()}`);
  }

  return response.json() as Promise<T>;
}
```

## Atlassian API Content Format

Jira and Confluence use the **Atlassian Document Format (ADF)** for rich text — NOT plain strings or Markdown:

```typescript
// ✅ Correct: ADF format for Jira comment body
const commentBody = {
  type: "doc",
  version: 1,
  content: [
    {
      type: "paragraph",
      content: [{ type: "text", text: "Your comment here" }]
    }
  ]
};

// ❌ Wrong: plain string (will be rejected by the API)
const commentBody = "Your comment here";
```

## Deployment

```bash
# Deploy to development environment (use this during hackathon)
cd packages/atlassian-agent && forge deploy --environment development
forge install --environment development --site $(ATLASSIAN_SITE)

# Or via Makefile:
make deploy-forge
```

## Known Gotchas

- **Rovo agents only see data in the app they're installed in.** A Jira-installed agent can't auto-read Confluence. You must explicitly call the `search-runbooks` Action which goes through the remote backend.
- **Forge function timeout is 25 seconds.** If the remote endpoint is slow, the action will time out. Keep remote calls under 15 seconds. Use async/streaming patterns if needed.
- **`forge.yml` manifest changes require a full redeploy.** Changes to action inputs or agent prompts don't hot-reload.
- **JSM API base URL differs from Jira.** Always use `requestServiceDesk` from `@forge/jira-service-desk-api`, not the generic Jira client, for JSM calls.
