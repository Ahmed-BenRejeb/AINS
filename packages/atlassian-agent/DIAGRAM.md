# atlassian-agent — Component Diagram (UC3 Forge)

> Code-accurate. Each ` ```mermaid ` block pastes directly into
> [mermaid.live](https://mermaid.live). Back to [system diagrams](../../DIAGRAMS.md).

## Module map (manifest → index → actions → lib)

```mermaid
flowchart TB
    MAN["manifest.yml<br/>rovo:agent 'sentinel-incident-agent'<br/>7 action + 7 function modules<br/>scopes: jira-work, confluence-content<br/>external.fetch.backend: remote.ahmedxsaad.me"]
    IDX["src/index.ts — re-exports 7 handlers (handler: index.<fn>)"]

    subgraph ACTIONS["src/actions/"]
        A1["fetchIncident"]
        A2["searchSimilarIncidents"]
        A3["searchRunbooks"]
        A4["postRcaComment"]
        A5["resolveDuplicate"]
        A6["draftPirPage"]
        A7["flagKnowledgeGap"]
    end
    subgraph LIB["src/lib/"]
        REM["remote.ts — callRemote (X-Sentinel-Secret + X-Account-Id, withBackoff)"]
        ATL["atlassian.ts — getIncident · addComment · linkIssues · createIncidentIssue · createConfluencePage"]
        ADF["adf.ts — rcaToAdf · pirToAdf · duplicateToAdf · adfToText"]
        BACK["backoff.ts — withBackoff (429)"]
        CTX["context.ts — accountIdOf"]
        CON["contract.ts — types mirroring trace_core/schema.ts"]
    end

    MAN --> IDX
    IDX --> ACTIONS
    A1 --> ATL
    A2 --> REM
    A3 --> REM
    A4 --> REM
    A4 --> ADF
    A5 --> REM
    A5 --> ATL
    A5 --> ADF
    A6 --> REM
    A6 --> ADF
    A7 --> ATL
    REM --> BACK
    ACTIONS --> CTX
    REM --> CON
```

## Action routing — native vs remote backend

```mermaid
flowchart LR
    subgraph Native["Atlassian-native (Forge sandbox only)"]
        N1["fetchIncident → requestJira GET issue"]
        N2["flagKnowledgeGap → createIncidentIssue (AO, type id 10013)"]
    end
    subgraph Remote["Delegate heavy compute → atlassian-remote"]
        R1["searchSimilarIncidents → POST /search index=incidents"]
        R2["searchRunbooks → POST /search index=runbooks"]
        R3["postRcaComment → POST /analyze → addComment(rcaToAdf)"]
        R4["draftPirPage → POST /analyze → createConfluencePage(pirToAdf)"]
        R5["resolveDuplicate → POST /duplicates"]
    end
    Native --> J[("Jira / JSM / Confluence<br/>@forge/api asApp()")]
    Remote -->|callRemote| B[("remote.ahmedxsaad.me")]
    Remote --> J
```

## `resolveDuplicate` — the only writer of the Jira link graph

```mermaid
flowchart TD
    S["resolveDuplicate(issueKey, context)"] --> AID["accountId = accountIdOf(context)"]
    AID --> CR["callRemote('duplicates', {incident_key, requested_by})"]
    CR --> CHK{"verdict.is_duplicate<br/>AND !flag_for_human<br/>AND verdict.duplicate_of?"}
    CHK -->|yes| LINK["linkIssues(issueKey, duplicate_of)<br/>POST /rest/api/3/issueLink type=ATLASSIAN_DUPLICATE_LINK_TYPE"]
    LINK --> CMT["addComment(duplicateToAdf) → linked=true"]
    CHK -->|no| SURF["addComment(candidates) — no link (graceful degradation)"]
    CMT --> OUT["{commentId, isDuplicate, duplicateOf, linked, flagForHuman}"]
    SURF --> OUT
```

## `callRemote` request shape

```mermaid
flowchart LR
    A["action"] --> CR["callRemote(endpoint, payload, accountId)"]
    CR --> BO["withBackoff (retry 429)"]
    BO --> F["fetch(FORGE_REMOTE_URL/endpoint)<br/>headers: Content-Type, X-Sentinel-Secret, X-Account-Id"]
    F --> CHK{"response.ok?"}
    CHK -->|yes| J["return parsed JSON as T"]
    CHK -->|no| ERR["throw Error(status)"]
```
