# deploy — Component Diagram (K8s · KEDA · Observability · Chaos)

> Kubernetes / Helm packaging of the platform with autoscaling, monitoring, and chaos tests.
> Each ` ```mermaid ` block pastes directly into [mermaid.live](https://mermaid.live).
> Back to the [system diagrams](../DIAGRAMS.md).

## Build & manifest layout

```mermaid
flowchart TB
    subgraph DOCKER["docker/"]
        PY["python.Dockerfile<br/>one image, all 3 FastAPI services"]
        DB["dashboard.Dockerfile<br/>Next.js"]
    end
    subgraph K8S["k8s/ (namespace: sentinel)"]
        NS["namespace.yaml"]
        CM["configmap.example.yaml + secret.example.yaml<br/>(gen-config.sh from .env)"]
        D1["eval-engine.yaml"]
        D2["flight-recorder.yaml"]
        D3["atlassian-remote.yaml"]
        D4["dashboard.yaml"]
        ST1["xqdrant.yaml"]
        ST2["minio.yaml"]
        KED["keda/scaledobject-eval-engine.yaml"]
        LOAD["load/load-generator.yaml"]
        KUST["kustomization.yaml"]
    end
    subgraph HELM["helm/sentinel/"]
        CH["Chart.yaml + values.yaml"]
        T["templates/: services · backends · dashboard · config · keda · servicemonitor"]
    end
    PY --> D1
    PY --> D2
    PY --> D3
    DB --> D4
    CM --> D1
    KED --> D1
```

## KEDA autoscaling (CPU trigger)

```mermaid
flowchart LR
    LG["load-generator"] --> SVC["eval-engine Service"]
    SVC --> POD["eval-engine pods"]
    POD --> CPU["CPU metric"]
    CPU --> SO["ScaledObject<br/>trigger: cpu 50%"]
    SO -->|"cpu 43% → 50%"| HPA["scale 1 → 3"]
    HPA --> POD
```

## Observability stack

```mermaid
flowchart TB
    subgraph SVCS["FastAPI services"]
        E["eval-engine /metrics"]
        F["flight-recorder /metrics"]
        R["atlassian-remote /metrics"]
    end
    SM["3× ServiceMonitor<br/>(scrape port http /metrics)"]
    PROM["kube-prometheus-stack<br/>(Prometheus)"]
    GRAF["Grafana dashboard<br/>(7 panels: replicas, CPU/mem, req rate, p95, restarts)"]
    E --> SM
    F --> SM
    R --> SM
    SM --> PROM
    PROM --> GRAF
```

## Chaos engineering (resilience proof)

```mermaid
flowchart LR
    subgraph Scripts["chaos/ (kubectl)"]
        PK["pod-kill.sh"]
        SS["steady-state.sh — availability check"]
    end
    subgraph Mesh["chaos/chaosmesh/"]
        CPK["pod-kill Schedule"]
        ND["network-delay"]
        CS["cpu-stress"]
    end
    PK --> HEAL["self-healing (Deployment recreates pod)"]
    CS --> SCALE["drives KEDA scale-out under load"]
    SS --> VERIFY["verdict: availability maintained"]
```
