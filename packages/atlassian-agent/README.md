# atlassian-agent

**UC3 — The Atlassian-native Forge app.**
Defines the Rovo AI Agent and its Actions. This is the only code that runs inside Atlassian's infrastructure.

---

## What Goes Here

- The Forge app manifest (`forge.yml`) defining the `rovo:agent` and `rovo:action` modules
- Action handlers: fetch-incident, search-similar-incidents, search-runbooks, post-rca-comment, draft-pir-page, flag-knowledge-gap
- Atlassian API wrappers (`@forge/api` — Jira, Confluence, JSM calls)
- The Forge Remote HTTP client (delegates heavy compute to `atlassian-remote`)
- Exponential backoff utility for Atlassian 429 rate limit responses

## What Does NOT Go Here

- Embedding or LLM calls — these go in `atlassian-remote` (Forge sandbox can't run them)
- Vector search — goes in `atlassian-remote`
- Eval logic — goes in `eval-engine`
- Any Python code — Forge requires TypeScript

## Why It Exists (and Why It's Separate from `atlassian-remote`)

Forge apps are TypeScript-only, run inside Atlassian's sandboxed AWS environment, and have strict limits (25-second timeout, no GPU, limited memory). This package contains **only what must run inside Atlassian's infrastructure**: reading/writing Jira/Confluence/JSM data and presenting the agent interface to end users. Everything computationally heavy is offloaded to `atlassian-remote` via Forge Remote HTTP calls. The two packages are in different languages, deployed differently, and have different constraints — they must stay separate.

## Structure

```
atlassian-agent/
├── forge.yml               Forge app manifest (rovo:agent, rovo:action modules)
├── package.json
├── tsconfig.json           strict TypeScript — "strict": true
├── src/
│   ├── index.ts            exports all action handlers
│   ├── actions/
│   │   ├── fetchIncident.ts
│   │   ├── searchSimilarIncidents.ts
│   │   ├── searchRunbooks.ts
│   │   ├── postRcaComment.ts
│   │   ├── draftPirPage.ts
│   │   └── flagKnowledgeGap.ts
│   └── lib/
│       ├── atlassian.ts    @forge/api wrappers
│       ├── remote.ts       Forge Remote fetch helper
│       └── backoff.ts      exponential backoff for 429 responses
└── tests/
    ├── *.test.ts
    └── __mocks__/
        └── @forge/api.ts   Forge API mock for tests
```

## Setup and Deploy

```bash
npm install -g @forge/cli
forge login

cd packages/atlassian-agent
pnpm install
pnpm test
pnpm typecheck

# Deploy to Atlassian dev environment
forge deploy --environment development
forge install --environment development --site https://your-site.atlassian.net
```

## Critical: Atlassian Document Format (ADF)

Jira and Confluence use ADF for rich text — **not** plain strings or Markdown:

```typescript
// Always use ADF format
const body = {
  type: "doc", version: 1,
  content: [{ type: "paragraph", content: [{ type: "text", text: "..." }] }]
};
```
