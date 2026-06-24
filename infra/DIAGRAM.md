# infra — Component Diagram (Cloudflare · Azure)

> The deployed runtime: Azure VM, Cloudflare Tunnel + Workers AI + D1.
> Each ` ```mermaid ` block pastes directly into [mermaid.live](https://mermaid.live).
> Back to the [system diagrams](../DIAGRAMS.md).

## Cloudflare resources

```mermaid
flowchart TB
    subgraph CF["Cloudflare (infra/cloudflare/)"]
        WT["wrangler.toml"]
        SQL["d1-schema.sql<br/>run_manifests · trace_records · eval_verdicts"]
        AI["Workers AI<br/>llama-3.1-8b-instruct-fp8-fast (RCA + judge)<br/>llama-guard-3-8b (safety)<br/>bge-base-en-v1.5 (768-dim embed)"]
        D1["D1 (SQLite) — sentinel-traces"]
        TUN["Tunnel: sentinel<br/>(cloudflared systemd unit)"]
    end
    SQL --> D1
    WT --> D1
```

## Azure VM topology (infra/azure/setup.sh)

```mermaid
flowchart TB
    subgraph VM["Azure VM 48.220.48.34 · Ubuntu 24.04 (only SSH:22 open)"]
        direction TB
        subgraph SYSTEMD["systemd units (EnvironmentFile=/srv/sentinel/.env)"]
            U1["sentinel-eval :8000"]
            U2["sentinel-remote :8080"]
            U3["sentinel-flight :8001"]
            U4["sentinel-dashboard :3001"]
        end
        subgraph DOCKER["Langfuse Docker stack"]
            LF["langfuse-web :3000"]
            MIN["MinIO :9090 (internal)"]
        end
        XQ["xqdrant :6333 (internal)"]
        CLOUD["cloudflared (tunnel agent)"]
    end
    U1 --- CLOUD
    U2 --- CLOUD
    U3 --- CLOUD
    U4 --- CLOUD
    LF --- CLOUD
```

## Ingress routing (Cloudflare Tunnel → internal ports)

```mermaid
flowchart LR
    subgraph Public["Public hostnames (CF managed challenge)"]
        H1["remote.ahmedxsaad.me"]
        H2["eval.ahmedxsaad.me"]
        H3["flight.ahmedxsaad.me"]
        H4["dashboard.ahmedxsaad.me"]
        H5["langfuse.ahmedxsaad.me"]
    end
    H1 --> P1[":8080 atlassian-remote"]
    H2 --> P2[":8000 eval-engine"]
    H3 --> P3[":8001 flight-recorder"]
    H4 --> P4[":3001 dashboard"]
    H5 --> P5[":3000 Langfuse"]

    note["xqdrant :6333 + MinIO :9090<br/>never exposed (internal localhost only)"]
```

## Where each store lives

```mermaid
flowchart LR
    APP["Sentinel services"]
    APP -->|trace metadata + verdicts| D1[("Cloudflare D1")]
    APP -->|cassette blobs| MIN[("MinIO on VM<br/>(R2 skipped — needs CC)")]
    APP -->|vector search| XQ[("xqdrant on VM<br/>(replaces Vectorize)")]
    APP -->|LLM / embed / safety| AI[("Workers AI")]
    APP -->|trace UI| LF[("Langfuse on VM")]
    APP -->|Jira / Confluence / JSM| ATL[("Atlassian Cloud<br/>ahmedains.atlassian.net")]
```
