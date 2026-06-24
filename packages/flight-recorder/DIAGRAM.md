# flight-recorder — Component Diagram (UC2)

> Code-accurate. Each ` ```mermaid ` block pastes directly into
> [mermaid.live](https://mermaid.live). Back to [system diagrams](../../DIAGRAMS.md).

## Module map

```mermaid
flowchart TB
    API["api.py — FastAPI :8001<br/>GET /health · GET /runs · GET /runs/{id}<br/>POST /replay · POST /bisect<br/>require_secret + valid_run_id"]

    subgraph PROXY["proxy/"]
        LLM["llm_proxy.py<br/>_RecordingCore + RecordingTransport (sync) + AsyncRecordingTransport"]
        MCP["mcp_interceptor.py<br/>@record_tool decorator"]
        CASS["cassette.py<br/>empty/load/save_to_cassette · append_record · normalize_request · hash_step_key"]
    end
    subgraph REPLAY["replay/"]
        ENG["engine.py<br/>replay_run · build_tape_agent · ReplayResult"]
        BIS["bisect.py<br/>bisect_runs · BisectResult"]
    end
    subgraph STORE["storage/"]
        D1["d1_client.py — insert / query (D1 REST)"]
        MIN["minio_client.py — store_blob / load_blob (boto3, NOT R2)"]
    end
    subgraph AUDIT["audit/"]
        HC["hash_chain.py<br/>build_payload · compute_payload_hash · sign · write_audit_record · verify_chain"]
    end
    CFG["config.py — resolve_mode · is_cf_workers_ai_url · GENESIS_PREV_HASH"]
    MAN["manifest.py — write_run_manifest"]
    LFC["langfuse_client.py — init_langfuse (best-effort)"]

    API --> ENG
    API --> BIS
    API --> CASS
    API --> D1
    LLM --> CASS
    LLM --> HC
    LLM --> CFG
    MCP --> CASS
    MCP --> HC
    ENG --> LLM
    ENG --> CASS
    BIS --> CASS
    CASS --> MIN
    HC --> D1
    MAN --> D1
```

## Transport request routing (`handle_request` / `handle_async_request`)

```mermaid
flowchart TD
    REQ["httpx request"] --> CF{"is_cf_workers_ai_url?<br/>host=api.cloudflare.com AND path has /ai/run/"}
    CF -->|no| FWD["_forward (live, live_call_count++)"]
    CF -->|yes| KEY["step_key = hash_step_key(normalize_request(req))"]
    KEY --> MODE{"resolve_mode()"}
    MODE -->|replay| REPL["_replay(step_key)"]
    MODE -->|passthrough| FWD
    MODE -->|record| RECRD["_record"]

    RECRD --> RFWD["_forward → read → _serialize_response"]
    RFWD --> PERS["_persist"]
    PERS --> WAL["write_audit_record (write-ahead → D1 trace_records)"]
    WAL --> SAVE["save_to_cassette (steps + records, → MinIO)"]
    SAVE --> REB["_rebuild_response"]

    REPL --> INJ{"step_key in injections?"}
    INJ -->|yes| OVR["return override (divergence editing) → injected_steps"]
    INJ -->|no| HIT{"step_key in cassette steps?"}
    HIT -->|yes| REB2["_rebuild_response from tape (0 live calls)"]
    HIT -->|no| MISS["raise CassetteMissError (diverged)"]
```

## Cassette structure & the two write paths

```mermaid
flowchart LR
    subgraph CASSETTE["{run_id}.json in MinIO"]
        V["version, run_id"]
        STEPS["steps{ step_key → stored response }  (replay/bisect read this)"]
        ORDER["order[ step_key, ... ]  (positional bisect)"]
        RECORDS["records[ full TraceRecord, ... ]  (non-lossy trace the eval engine loads)"]
    end
    P1["save_to_cassette (HTTP step)"] --> STEPS
    P1 --> ORDER
    P1 --> RECORDS
    P2["append_record / record_event (semantic tool_call, e.g. xqdrant search)"] --> RECORDS
```

## Audit hash-chain (tamper-evident, write-ahead)

```mermaid
flowchart LR
    G["GENESIS_PREV_HASH = sha256:000...0"] --> S0
    subgraph S0["step 0"]
        P0["payload (run_id, step_id, seq, kind, input, output, prev_hash)"]
        H0["payload_hash = sha256_hex(canonical_json)"]
        M0["hmac = HMAC-SHA256(payload_hash, AUDIT_HMAC_KEY)"]
    end
    S0 -->|"prev_hash = payload_hash"| S1["step 1"]
    S1 --> S2["step 2 ... step N"]
    S2 -.verify.-> VC["verify_chain: recompute hashes + check links"]
```

## Replay, inject & bisect (the API surface)

```mermaid
flowchart TB
    subgraph Replay["POST /replay (run_id, inject?)"]
        R1["load_cassette → records"] --> R2["build_tape_agent: re-issue recorded llm_call requests in order"]
        R2 --> R3["RecordingTransport(mode=replay, injections)"]
        R3 --> R4["ReplayResult: recorded_steps, live_call_count==0,<br/>diverged, injected_steps, output_preview, original_outputs"]
    end
    subgraph Bisect["POST /bisect (good_run_id, bad_run_id)"]
        B1["walk both order[] positionally"] --> B2{"compare"}
        B2 -->|"good_key != bad_key"| B3["request diverged"]
        B2 -->|"same key, different response"| B4["response diverged (non-determinism)"]
        B2 -->|"length differs"| B5["run length diverged"]
        B3 --> BR["BisectResult: first_diverging_step, reason, good_rca, bad_rca"]
        B4 --> BR
        B5 --> BR
    end
```

## `@record_tool` (function/MCP interception, separate from the HTTP proxy)

```mermaid
flowchart TD
    CALL["wrapped tool call (args, kwargs)"] --> K["step_key = hash_step_key(normalize_request({tool, args, kwargs}))"]
    K --> M{"resolve_mode"}
    M -->|replay| L["return cassette steps[key]['result'] (no real call)"]
    M -->|passthrough| F["call real func"]
    M -->|record| R["call func → write_audit_record(kind=tool_call) → save_to_cassette"]
```
