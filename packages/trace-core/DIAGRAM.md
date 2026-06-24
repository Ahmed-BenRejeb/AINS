# trace-core — Component Diagram

> Code-accurate. Imported by everyone; imports nothing local. Each ` ```mermaid `
> block pastes directly into [mermaid.live](https://mermaid.live).
> Back to [system diagrams](../../DIAGRAMS.md).

## Module map (what `__init__.py` re-exports)

```mermaid
flowchart TB
    INIT["__init__.py — flat re-exports (from trace_core import ...)"]

    subgraph CONST["constants.py"]
        C1["PASS_AT_K_TRIALS=8 · CONFIDENCE_THRESHOLD=0.70"]
        C2["DUPLICATE_CONFIDENCE_THRESHOLD=0.85"]
        C3["VECTOR_SIMILARITY_THRESHOLD=0.75 · MAX_RETRIEVAL_RESULTS=5"]
        C4["CASSETTE_VERSION=1 · HASH_ALGORITHM · HASH_PREFIX='sha256:'"]
        C5["AUDIT_HMAC_ALGORITHM · VOLATILE_REQUEST_FIELDS · LOG_LEVEL"]
    end
    subgraph HASH["hash_utils.py"]
        H1["normalize_request → _strip_volatile → canonical_json"]
        H2["hash_step_key → sha256_hex"]
    end
    subgraph OTEL["otel.py (gen_ai.* + gen_ai.replay.*)"]
        O1["emit_llm_call_span"]
        O2["emit_tool_call_span"]
        O3["emit_agent_run_span"]
    end
    subgraph SCHEMA["schema.py  ⇄  schema.ts (mirror)"]
        S1["TraceRecord · StepMetadata · AuditBlock · RunManifest"]
        S2["EvalVerdict · DimensionScore · FailureAttribution · SelfEvaluation"]
        S3["DriftReport · EvaluatorQuality"]
        S4["SearchResult · Attribution"]
        S5["RcaDraft · DuplicateVerdict"]
        S6["Literals: StepKind · FlightMode · RunStatus · VerdictLabel · SeverityLevel"]
    end

    INIT --> CONST
    INIT --> HASH
    INIT --> OTEL
    INIT --> SCHEMA
    HASH -->|uses| CONST
    OTEL -->|opt-in gen_ai_latest_experimental| EXT(("OpenTelemetry SDK"))
```

## Cassette-key hashing pipeline (the stability contract)

```mermaid
flowchart LR
    REQ["request mapping<br/>(method, path, body)"] --> SV["_strip_volatile<br/>drop timestamp / request_id / nonce / trace_id / span_id"]
    SV --> CJ["canonical_json<br/>sorted keys, compact separators"]
    CJ --> NR["normalize_request → str"]
    NR --> SX["sha256_hex → 'sha256:...'"]
    SX --> KEY["hash_step_key = cassette lookup key"]
    KEY -.->|"any change here ⇒ bump CASSETTE_VERSION"| CV["CASSETTE_VERSION"]
```

## Core schema relationships

```mermaid
classDiagram
    class TraceRecord {
        str run_id
        str step_id
        int sequence
        datetime timestamp
        StepKind kind
        dict input
        dict output
    }
    class StepMetadata {
        str model_id
        str tool_name
        float latency_ms
        dict sampling_params
    }
    class AuditBlock {
        str prev_hash
        str payload_hash
        str hmac
    }
    class RunManifest {
        str run_id
        FlightMode flight_mode
        str cassette_id
        int step_count
        RunStatus status
    }
    class EvalVerdict {
        str run_id
        int trial_number
        VerdictLabel verdict
        str replay_link
        str recommended_action
    }
    TraceRecord --> StepMetadata
    TraceRecord --> AuditBlock
    EvalVerdict --> "*" DimensionScore
    EvalVerdict --> "0..1" FailureAttribution
    EvalVerdict --> SelfEvaluation
    SearchResult --> Attribution
```

## Who imports which symbols

```mermaid
flowchart LR
    TC["trace-core"]
    TC -->|"TraceRecord, hash_step_key, normalize_request, FlightMode, AuditBlock"| FR["flight-recorder"]
    TC -->|"EvalVerdict, DriftReport, EvaluatorQuality, TraceRecord, *_THRESHOLD"| EE["eval-engine"]
    TC -->|"RcaDraft, DuplicateVerdict, SearchResult, RunManifest, MAX_RETRIEVAL_RESULTS"| AR["atlassian-remote"]
    TC -.->|"schema.ts → contract.ts"| AA["atlassian-agent"]
    TC -.->|"schema.ts → lib/types.ts"| DB["dashboard"]
```

**Rule:** edit `schema.py` → edit `schema.ts` in the same commit; edit the hashing/normalization → bump `CASSETTE_VERSION`.
