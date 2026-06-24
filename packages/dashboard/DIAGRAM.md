# dashboard — Component Diagram (UI)

> Code-accurate to `lib/api.ts` + the `app/` routes. Each ` ```mermaid ` block
> pastes directly into [mermaid.live](https://mermaid.live).
> Back to [system diagrams](../../DIAGRAMS.md).

## Routes & data accessors

```mermaid
flowchart TB
    subgraph APP["app/ (server components, Next.js 16)"]
        P0["/ page.tsx → getOverview"]
        P1["/runs → getRuns"]
        P2["/runs/[run_id] → getRunDetail"]
        P3["/verdicts/[run_id] → getVerdict"]
        P4["/replay/[run_id] → getRunDetail + postReplay/postBisect"]
        P5["/reliability"]
        P6["/drift → getDrift"]
        P7["/evaluator → getEvaluatorQuality"]
        RT["api/{replay,bisect,evaluator-quality}/route.ts (server POST proxies)"]
    end

    subgraph LIB["lib/api.ts accessors → Loaded<T>{data, source}"]
        F1["getRuns / getRunDetail"]
        F2["getVerdict / getVerdictSummaries / getOverview"]
        F3["postReplay / postBisect"]
        F4["getDrift / getEvaluatorQuality"]
    end

    P0 --> F2
    P1 --> F1
    P2 --> F1
    P3 --> F2
    P4 --> F1
    P4 --> RT
    P5 --> F4
    P6 --> F4
    P7 --> F4
    RT --> F3
```

## Each accessor → live service endpoint

```mermaid
flowchart LR
    subgraph FR["flight-recorder (FLIGHT_RECORDER_API)"]
        E1["GET /runs"]
        E2["GET /runs/{id}"]
        E3["POST /replay"]
        E4["POST /bisect"]
    end
    subgraph EE["eval-engine (EVAL_ENGINE_API)"]
        E5["GET /verdicts?limit"]
        E6["GET /verdicts/{id}"]
        E7["POST /drift"]
        E8["GET /evaluator-quality/demo"]
    end
    getRuns --> E1
    getRunDetail --> E2
    postReplay --> E3
    postBisect --> E4
    getVerdictSummaries --> E5
    getVerdict --> E6
    getDrift --> E5
    getDrift --> E7
    getEvaluatorQuality --> E8
```

## Server-side fetch with mock fallback (the demo safety net)

```mermaid
flowchart TD
    REQ["accessor(useMock)"] --> MQ{"useMock (?mock=true)?"}
    MQ -->|yes| FIX["return mock fixture · source = mock"]
    MQ -->|no| LIVE["fetchJson(INTERNAL_URL, X-Sentinel-Secret, timeout)"]
    LIVE --> OK{"2xx within budget?<br/>5s list/detail · 30s replay/bisect"}
    OK -->|yes| DATA["live(data) · source = live"]
    OK -->|"no / timeout / non-2xx"| FB["fallback(mock, error) · source = mock-fallback"]
    DATA --> BADGE["DataSourceBadge: LIVE / MOCK / FALLBACK"]
    FIX --> BADGE
    FB --> BADGE
```

## `getOverview` — per-run aggregation (pass-rate / true pass^k)

```mermaid
flowchart TD
    O["getOverview"] --> PAR["Promise.all(getRuns, getVerdictSummaries(200))"]
    PAR --> COLD{"both missed?"}
    COLD -->|yes| RETRY["wait 600ms, retry once"]
    RETRY --> EMPTY{"still both missed?"}
    EMPTY -->|yes| HONEST["honest empty: zeros + mock-fallback (NOT mock fixtures)"]
    EMPTY -->|no| GRP
    COLD -->|no| GRP["group verdicts by run_id (a run has many trials)"]
    GRP --> M["pass_rate = latest verdict pass / evaluated<br/>pass_hat_k = runs where ALL trials pass<br/>flagged = runs with any flag_for_human"]
    M --> STATS["OverviewStats + recent verdict table"]
```

## URL split (public links vs internal fetches)

```mermaid
flowchart LR
    subgraph Public["NEXT_PUBLIC_* (sent to browser, clickable links)"]
        U1["FLIGHT_RECORDER_URL"]
        U2["EVAL_ENGINE_URL"]
        U3["LANGFUSE_URL · DASHBOARD_URL"]
    end
    subgraph Internal["server-side only (never reaches browser)"]
        I1["FLIGHT_RECORDER_INTERNAL_URL → 127.0.0.1:8001"]
        I2["EVAL_ENGINE_INTERNAL_URL → 127.0.0.1:8000"]
        I3["FORGE_REMOTE_SECRET → X-Sentinel-Secret"]
    end
    Public --> LINKS["replay deep-link, Langfuse"]
    Internal --> FETCH["fetchJson (real data, no tunnel hop)"]
```

## Components (`components/sentinel/`)

```mermaid
flowchart TB
    subgraph UI["components/ui/ (hand-rolled shadcn)"]
        PRIM["card · badge · button · table · skeleton · progress"]
    end
    subgraph SEN["components/sentinel/"]
        VW["views/*View + HomeLanding"]
        VC["VerdictCard"]
        DT["DimensionTable"]
        AB["AttributionBox"]
        ST["StepTimeline (operation-aware: embedding/chat/tool_call)"]
        RSB["RunStatusBadge"]
        RR["ReliabilityRing (pass-rate gauge)"]
        MO["motion.tsx (PageTransition / Tilt / stagger)"]
    end
    VW --> VC
    VW --> ST
    VW --> RSB
    VW --> RR
    VW --> MO
    VC --> DT
    VC --> AB
    SEN --> UI
```
