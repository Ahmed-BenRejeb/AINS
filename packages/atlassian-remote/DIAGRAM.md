# atlassian-remote — Component Diagram (UC3 backend)

> Code-accurate. Each ` ```mermaid ` block pastes directly into
> [mermaid.live](https://mermaid.live). Back to [system diagrams](../../DIAGRAMS.md).

## Module map

```mermaid
flowchart TB
    API["api.py — FastAPI :8080<br/>GET /health · POST /analyze · POST /duplicates<br/>POST /search · POST /embed<br/>verify_request (X-Sentinel-Secret + X-Account-Id) · httpx error → 503"]

    AN["analyzer.py<br/>analyze_incident · resolve_incident_duplicate · extract_incident_text (ADF flatten)"]
    REC["recording.py<br/>RunRecorder · record_tool_call · persist_manifest · new_run_id"]
    EC["eval_client.request_evaluation"]
    VS["vector_search.py<br/>search_similar · cf_ai_embed_query · _build_attribution"]
    RCA["rca_generator.py<br/>generate_rca · build_rca_prompt · needs_human_review"]
    DUP["duplicate_resolver.py<br/>resolve_duplicate · needs_human_review"]
    ACL["atlassian_client.AtlassianClient.get_issue (429 backoff)"]
    CF["cf_ai_client.py<br/>cf_ai_chat · cf_ai_embed · _post (retry) · using_transport (contextvar)"]
    MOD["models.py — AnalyzeResult · DuplicateResult"]
    CFG["config.py — thresholds, urls, collections"]

    API --> AN
    API --> VS
    API --> CF
    AN --> ACL
    AN --> REC
    AN --> VS
    AN --> RCA
    AN --> DUP
    AN --> EC
    RCA --> CF
    DUP --> CF
    VS --> CF
    VS --> XQ[("xqdrant :6333<br/>query_points")]
    CF --> AI[("CF Workers AI")]
    REC -->|AsyncRecordingTransport| FR["flight-recorder"]
    EC --> EE["eval-engine :8000"]
```

## `/analyze` — the Phase 4 loop (`analyze_incident`)

```mermaid
sequenceDiagram
    autonumber
    participant AN as analyze_incident
    participant ACL as AtlassianClient
    participant REC as RunRecorder
    participant CF as cf_ai_client
    participant XQ as vector_search
    participant RCA as rca_generator
    participant EC as eval_client

    AN->>AN: run_id = new_run_id()
    AN->>ACL: get_issue(incident_key) → extract_incident_text (ADF→text)
    AN->>REC: with RunRecorder(run_id)  [using_transport binds AsyncRecordingTransport]
    AN->>CF: cf_ai_embed_query(incident_text)  [taped HTTP step]
    AN->>XQ: search_similar(incidents, embedding=...)
    AN->>REC: record_tool_call(xqdrant.query_points incidents)  [record_event]
    AN->>XQ: search_similar(runbooks, embedding=...)  [reuses same vector]
    AN->>REC: record_tool_call(xqdrant.query_points runbooks)
    AN->>RCA: generate_rca(text, similar, runbooks) → cf_ai_chat → RcaDraft  [taped]
    Note over AN: exit RunRecorder context (transport unbound)
    AN->>REC: persist_manifest(run_id, step_count, task_id)  [→ D1, best-effort]
    AN->>EC: request_evaluation(run_id) → POST /evaluate  [best-effort, may be None]
    AN-->>AN: AnalyzeResult{run_id, rca_draft, similar, runbooks,<br/>flag_for_human=needs_human_review(draft), eval_verdict, replay_link}
```

## `/duplicates` — graceful-degradation gate

```mermaid
flowchart TD
    IN["resolve_incident_duplicate(incident_key)"] --> TXT["get_issue → extract_incident_text"]
    TXT --> SR["search_similar(incidents only, k)"]
    SR --> JR["resolve_duplicate → cf_ai_chat → DuplicateVerdict"]
    JR --> NHR{"needs_human_review?<br/>not is_duplicate OR no duplicate_of OR confidence < 0.85"}
    NHR -->|false| AUTO["flag_for_human=false<br/>(agent will linkIssues + comment)"]
    NHR -->|true| HUMAN["flag_for_human=true<br/>(surface candidates only)"]
    AUTO --> RES["DuplicateResult{verdict, similar, flag_for_human}"]
    HUMAN --> RES
```

## `vector_search.search_similar` (xqdrant + always-on attribution)

```mermaid
flowchart TD
    Q["search_similar(query_text, collection, k, embedding?)"] --> FL["floor = similarity_threshold(collection)<br/>incidents 0.75 · runbooks 0.60"]
    FL --> EMB{"embedding given?"}
    EMB -->|no| E["cf_ai_embed_query → 768-dim"]
    EMB -->|yes| QP
    E --> QP["get_client().query_points(collection, query=vec, with_payload)"]
    QP --> LOOP["for each ScoredPoint"]
    LOOP --> THR{"point.score > floor?"}
    THR -->|no| SKIP["drop (xqdrant returns weak matches too)"]
    THR -->|yes| ATTR["_build_attribution<br/>payload block, else synth confidence_margin = gap to next hit"]
    ATTR --> SR["SearchResult(id, text, score, attribution)"]
    QP -.langfuse span 'xqdrant-search'.-> LF["Langfuse"]
```

## `cf_ai_client._post` — retry / quota / recording transport

```mermaid
flowchart TD
    P["_post(model, payload)"] --> TX["httpx.AsyncClient(transport = _active_transport.get())"]
    TX --> POST["POST {cf_ai_url}/{model}  Bearer token"]
    POST --> ST{"status"}
    ST -->|2xx| OK["return result"]
    ST -->|429 + code 4006 'neurons'| FAST["_is_quota_exhausted → raise (fail fast, no retry)"]
    ST -->|429 burst| R1["sleep 30s ×3 then raise"]
    ST -->|5xx| R2["sleep 5s ×2 then raise"]
    ST -->|other| RAISE["raise HTTPStatusError → api 503"]
    OK --> RT["cf_ai_chat → _response_text (response / choices / reasoning)"]
```
