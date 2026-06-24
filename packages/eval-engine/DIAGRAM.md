# eval-engine — Component Diagram (UC1)

> Code-accurate. Each ` ```mermaid ` block pastes directly into
> [mermaid.live](https://mermaid.live). Back to [system diagrams](../../DIAGRAMS.md).

## Module map

```mermaid
flowchart TB
    API["api.py — FastAPI :8000<br/>GET /health · GET /verdicts · GET /verdicts/{id}<br/>POST /evaluate · POST /evaluate/batch<br/>POST /drift · POST /evaluator-quality · GET /evaluator-quality/demo<br/>require_secret · valid_run_id · httpx error → 503"]

    REP["verdicts/reporter.py<br/>evaluate_run · evaluate_gold_set · _file_issue"]
    TL["trace_loader.load_trace"]
    CS["cassette_store.load_cassette_records (boto3 MinIO)"]
    VS["verdict_store — persist_verdict / list_verdicts / get_verdict (D1)"]
    TRN["transcript.build_transcript"]

    subgraph GR["graders/"]
        SF["safety_filter.check_safety (Llama Guard 3)"]
        CG["code_grader.grade (5 deterministic checks)"]
        JG["llm_judge.calibrated_judge → judge ×2"]
    end
    AT["attribution/dag_attributor.attribute_failure"]
    subgraph ME["metrics/"]
        PK["pass_at_k.pass_at_k / consistency_rate"]
        EQ["evaluator_quality.cohen_kappa / score_evaluator"]
    end
    subgraph DR["drift/"]
        DET["detector.detect_drift"]
        EMB["embedder.embed_centroid / cosine_distance"]
    end
    CF["cf_ai_client.cf_ai_chat / cf_ai_embed / cf_ai_safety"]
    ACL["verdicts/atlassian_client.create_eval_issue"]

    API --> REP
    API --> DET
    API --> EQ
    API --> VS
    API --> TL
    TL --> CS
    REP --> TRN
    REP --> SF
    REP --> CG
    REP --> JG
    REP --> AT
    REP --> VS
    REP --> ACL
    REP -->|gold set| EQ
    SF --> CF
    JG --> CF
    EMB --> CF
    DET --> EMB
```

## `evaluate_run` pipeline (one trial → one EvalVerdict)

```mermaid
flowchart TD
    START["evaluate_run(run_id, trial, records)"] --> TRN["build_transcript(records)"]
    TRN --> SAFE["check_safety (Llama Guard 3)"]
    TRN --> CODE["code_grader.grade(records)"]
    SAFE --> SQ{"safe?"}
    SQ -->|no| FF["verdict=fail (skip judge)<br/>safety DimensionScore, confidence 1.0"]
    SQ -->|yes| JUDGE["calibrated_judge(transcript, rubric)"]
    JUDGE --> COMB["_combine_verdict(code_result, judge)<br/>uncertain wins → else any fail → else pass"]
    COMB --> FLAG["flag_for_human = judge.flag OR confidence < 0.70"]
    FF --> ATTR
    FLAG --> ATTR{"verdict != pass?"}
    ATTR -->|yes| AT["attribute_failure(records)"]
    ATTR -->|no| SE
    AT --> SE["SelfEvaluation(judge_confidence, self_critique, flag_for_human)"]
    SE --> EV["assemble EvalVerdict (+ replay_link, recommended_action)"]
    EV --> PV["persist_verdict → D1 eval_verdicts (best-effort)"]
    PV --> FI{"file_issue AND (fail OR flagged)?"}
    FI -->|yes| JIRA["_file_issue → create AO Incident (best-effort)"]
    FI -->|no| DONE["return EvalVerdict"]
    JIRA --> DONE
```

## Calibrated LLM judge (mandatory position-bias calibration)

```mermaid
flowchart TD
    IN["calibrated_judge(transcript, rubric)"] --> P1["judge(transcript, rubric)"]
    IN --> P2["judge(transcript, _reorder_rubric(rubric))  (dimensions reversed)"]
    P1 --> J1["cf_ai_chat → _JudgeRawOutput<br/>verdict = mean(dim scores) ≥ JUDGE_PASS_THRESHOLD 0.6"]
    P2 --> J2["cf_ai_chat → derived verdict"]
    J1 --> CMP{"primary.verdict == swapped.verdict?"}
    J2 --> CMP
    CMP -->|no| UNC["verdict=uncertain, flag_for_human=true<br/>reason=position_bias_detected"]
    CMP -->|yes| OK["keep verdict, confidence=mean(both)"]
```

## Code grader (5 deterministic checks; score = fraction passing)

```mermaid
flowchart LR
    G["grade(records)"] --> C1["_check_schema<br/>llm_call has model_id, tool_call has tool_name"]
    G --> C2["_check_tool_calls<br/>has arguments, no error output"]
    G --> C3["_check_outcome<br/>create-issue produced key/id"]
    G --> C4["_check_loops<br/>< MAX_REPEATED_STEPS identical steps"]
    G --> C5["_check_token_budget<br/>sum total_tokens ≤ TOKEN_BUDGET"]
    C1 --> R["CodeGraderResult(passed = no failures, score = passed/5)"]
    C2 --> R
    C3 --> R
    C4 --> R
    C5 --> R
```

## DAG failure attribution (VeriLA-style)

```mermaid
flowchart TD
    A["attribute_failure(records)"] --> S["sort by sequence, walk in order"]
    S --> CLS["classify_component<br/>tool_call+search→retrieval · tool_call→execution · else→planning"]
    CLS --> SIG{"_failure_signal?"}
    SIG -->|"output.error / success=false"| E1["confidence 0.9"]
    SIG -->|"retrieval results == []"| E2["confidence 0.7"]
    SIG -->|"execution has no key/id/success"| E3["confidence 0.7"]
    SIG -->|"none → blame last step"| E4["confidence 0.5 (fallback)"]
    E1 --> FA["FailureAttribution(step, component, description, confidence)"]
    E2 --> FA
    E3 --> FA
    E4 --> FA
```

## Drift (`/drift`) & evaluator quality (`/evaluator-quality`)

```mermaid
flowchart LR
    subgraph Drift["detect_drift(baseline, current, outputs?)"]
        D1["pass-rate delta"] --> DD["drift_detected = any signal ≥ DRIFT_* threshold<br/>drift_score = max(signals)"]
        D2["per-dimension mean deltas → most_shifted_dimension"] --> DD
        D3["semantic: embed_centroid + cosine_distance (BGE)"] --> DD
        DD --> DR["DriftReport (+ human summary)"]
    end
    subgraph EvalQ["evaluate_gold_set(cases)"]
        G1["evaluate_run per GoldCase (file_issue=false)"] --> G2["predicted vs gold labels"]
        G2 --> G3["score_evaluator: accuracy + cohen_kappa<br/>+ per_label_recall + Landis & Koch band"]
        G3 --> EQR["EvaluatorQuality"]
    end
```

## Trace loading (cassette first, D1 previews fallback)

```mermaid
flowchart TD
    LT["load_trace(run_id)"] --> CR["cassette_store.load_cassette_records (MinIO {run_id}.json)"]
    CR --> Q{"records present?"}
    Q -->|yes| OK["sort by sequence → TraceRecord[]"]
    Q -->|no| FB["GET {FLIGHT_RECORDER_URL}/runs/{id} → trace rows → _row_to_record (500-char previews)"]
```
