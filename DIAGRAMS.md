# Sentinel — System Diagrams

> Diagrams derived from the actual source (not just the docs). Every fenced
> ` ```mermaid ` block below is a **standalone** diagram: copy the lines between the
> fences and paste them straight into the [Mermaid Live Editor](https://mermaid.live).
>
> Per-component internals each have their own `DIAGRAM.md`:
> [trace-core](packages/trace-core/DIAGRAM.md) ·
> [flight-recorder](packages/flight-recorder/DIAGRAM.md) ·
> [eval-engine](packages/eval-engine/DIAGRAM.md) ·
> [atlassian-remote](packages/atlassian-remote/DIAGRAM.md) ·
> [atlassian-agent](packages/atlassian-agent/DIAGRAM.md) ·
> [dashboard](packages/dashboard/DIAGRAM.md) ·
> [deploy](deploy/DIAGRAM.md) ·
> [infra](infra/DIAGRAM.md)

---

## 1. High-level system (the three use cases as one loop)

```mermaid
flowchart TB
    subgraph ATL["Atlassian Cloud (ahmedains.atlassian.net)"]
        JSM["Jira / JSM / Confluence"]
        AGENT["atlassian-agent (Forge, TypeScript)<br/>Rovo agent 'Sentinel Incident Responder'<br/>7 actions"]
        JSM <--> AGENT
    end

    subgraph VM["Azure VM (services behind Cloudflare Tunnel)"]
        REMOTE["atlassian-remote :8080<br/>/analyze /duplicates /search /embed"]
        FLIGHT["flight-recorder :8001<br/>/runs /replay /bisect"]
        EVAL["eval-engine :8000<br/>/evaluate /drift /evaluator-quality /verdicts"]
        DASH["dashboard :3001 (Next.js)"]
        LF["Langfuse :3000"]
        XQ["xqdrant :6333 (internal)"]
        MINIO["MinIO :9090 (internal)"]
    end

    subgraph CF["Cloudflare"]
        AI["Workers AI<br/>llama-3.1-8b-instruct-fp8-fast (chat)<br/>bge-base-en-v1.5 (embed)<br/>llama-guard-3-8b (safety)"]
        D1["D1: run_manifests, trace_records, eval_verdicts"]
    end

    AGENT -->|"callRemote: X-Sentinel-Secret + X-Account-Id"| REMOTE
    REMOTE -->|cf_ai_embed / cf_ai_chat| AI
    REMOTE -->|search_similar query_points| XQ
    REMOTE -->|"RunRecorder taping (UC2)"| FLIGHT
    REMOTE -->|"request_evaluation POST /evaluate"| EVAL

    FLIGHT -->|cassette blobs| MINIO
    FLIGHT -->|"audit chain + manifest"| D1
    EVAL -->|"safety + calibrated judge"| AI
    EVAL -->|load_cassette_records| MINIO
    EVAL -->|persist_verdict| D1
    EVAL -->|"_file_issue on fail/flag"| JSM

    REMOTE -.langfuse.-> LF
    EVAL -.langfuse.-> LF
    FLIGHT -.langfuse.-> LF

    DASH -->|"/runs /replay /bisect"| FLIGHT
    DASH -->|"/verdicts /drift /evaluator-quality"| EVAL
    DASH -.deep links.-> LF
```

---

## 2. Package dependency graph (enforced, no cycles)

```mermaid
flowchart TD
    TC["trace-core<br/>types + constants + hash_utils + otel"]
    FR["flight-recorder (UC2)"]
    EE["eval-engine (UC1)"]
    AR["atlassian-remote (UC3 backend)"]
    AA["atlassian-agent (UC3 Forge, TS)"]
    DB["dashboard (Next.js)"]
    MINIO[("MinIO cassette")]

    TC --> FR
    TC --> EE
    TC --> AR
    FR -->|"AsyncRecordingTransport + write_run_manifest"| AR
    EE -.->|"reads cassette over S3, not an import"| MINIO
    AA -.->|"HTTP only (callRemote)"| AR
    DB -.->|"types mirror schema.ts + HTTP"| FR
    DB -.-> EE

    classDef shared fill:#0f3,stroke:#0a0,color:#000;
    class TC shared;
```

---

## 3. End-to-end data flow: `POST /analyze` → recorded + judged verdict

```mermaid
sequenceDiagram
    autonumber
    participant AG as atlassian-agent
    participant API as atlassian-remote api.py
    participant AN as analyzer.analyze_incident
    participant JIRA as AtlassianClient
    participant REC as RunRecorder (UC2)
    participant CF as cf_ai_client
    participant XQ as vector_search / xqdrant
    participant RCA as rca_generator
    participant EC as eval_client
    participant EE as eval-engine

    AG->>API: POST /analyze {incident_key, requested_by}
    API->>API: verify_request (X-Sentinel-Secret)
    API->>AN: analyze_incident()
    AN->>JIRA: get_issue → extract_incident_text (flatten ADF)
    AN->>REC: run_id = new_run_id(), then with RunRecorder(run_id)
    Note over REC,CF: using_transport binds AsyncRecordingTransport via contextvar
    AN->>CF: cf_ai_embed_query(incident_text)  [taped step]
    AN->>XQ: search_similar(incidents, embedding)  [tool_call record_event]
    AN->>XQ: search_similar(runbooks, embedding)  [tool_call record_event]
    AN->>RCA: generate_rca → cf_ai_chat → RcaDraft  [taped step]
    AN->>REC: persist_manifest (run_manifests D1 row)
    AN->>EC: request_evaluation(run_id)
    EC->>EE: POST /evaluate {run_id}
    EE-->>EC: EvalVerdict (or files AO Incident on fail/flag)
    EC-->>AN: eval_verdict (best-effort, may be None)
    AN-->>AG: AnalyzeResult{run_id, rca_draft, similar, runbooks,<br/>flag_for_human, eval_verdict, replay_link}
```

---

## 4. Deployment topology

```mermaid
flowchart LR
    subgraph Forge["Atlassian Forge (nodejs22.x)"]
        AA["atlassian-agent<br/>forge deploy -e development"]
    end
    subgraph Tunnel["Cloudflare Tunnel 'sentinel'"]
        I1["remote.ahmedxsaad.me"]
        I2["eval.ahmedxsaad.me"]
        I3["flight.ahmedxsaad.me"]
        I4["dashboard.ahmedxsaad.me"]
        I5["langfuse.ahmedxsaad.me"]
    end
    subgraph AzureVM["Azure VM 48.220.48.34 (only SSH:22 open)"]
        S1["sentinel-remote.service :8080"]
        S2["sentinel-eval.service :8000"]
        S3["sentinel-flight.service :8001"]
        S4["sentinel-dashboard.service :3001"]
        DK["Docker: Langfuse :3000 + MinIO :9090 + xqdrant :6333"]
    end

    AA --> I1
    I1 --> S1
    I2 --> S2
    I3 --> S3
    I4 --> S4
    I5 --> DK
```
