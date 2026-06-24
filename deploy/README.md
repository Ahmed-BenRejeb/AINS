# Sentinel on Kubernetes (Minikube) + KEDA

Proves the platform **scales horizontally**: the three FastAPI services plus the
dashboard run as Deployments in a dedicated `sentinel` namespace, and **KEDA
autoscales the eval engine under load** (Phase 2). Everything here is self-contained
under `deploy/` — it does not change how the app runs on the VM.

```
deploy/
├── docker/        python.Dockerfile (one image, all 3 FastAPI services) + dashboard.Dockerfile
├── k8s/           namespace, config/secret (+ generator), backends, service Deployments, kustomization
│   ├── keda/      ScaledObject (Phase 2)
│   └── load/      load generator (Phase 2)
├── helm/          Helm chart (Phase 3)
├── observability/ kube-prometheus-stack values + ServiceMonitors + Grafana dashboard (Phase 4)
└── chaos/         pod-kill / steady-state scripts + Chaos Mesh experiments (Phase 5)
```

## What runs where
| In-cluster | External (via Secret/ConfigMap) |
|---|---|
| eval-engine `:8000`, flight-recorder `:8001`, atlassian-remote `:8080`, dashboard `:3001` | Cloudflare Workers AI, Cloudflare D1 |
| xqdrant `:6333`, MinIO `:9000` | Langfuse |

The Forge app (`atlassian-agent`) is **not** containerized — it runs on Atlassian's
Forge cloud, not here.

## Prerequisites
`docker`, `minikube`, `kubectl`, `helm`, and a repo-root `.env` (copy `.env.example`).

## Phase 1 — build + deploy

```bash
# 1. Start the cluster + metrics (metrics-server is needed for KEDA in Phase 2)
minikube start
minikube addons enable metrics-server

# 2. Build the images straight into Minikube's docker daemon
eval "$(minikube docker-env)"
docker build -f deploy/docker/python.Dockerfile    -t sentinel-python:dev .
docker build -f deploy/docker/dashboard.Dockerfile -t sentinel-dashboard:dev .

# 3. Generate the (gitignored) ConfigMap + Secret from your .env
bash deploy/k8s/gen-config.sh        # writes deploy/k8s/{configmap,secret}.yaml

# 4. Deploy everything into the `sentinel` namespace
kubectl apply -k deploy/k8s
kubectl -n sentinel get pods -w      # wait for all Running

# 5. Smoke-test a service
kubectl -n sentinel port-forward svc/eval-engine 8000:8000 &
curl -s localhost:8000/health        # -> {"status":"ok"}
```

> No real secrets handy? `cp deploy/k8s/configmap.example.yaml deploy/k8s/configmap.yaml`
> and `cp deploy/k8s/secret.example.yaml deploy/k8s/secret.yaml` — the services boot and
> `/health` works; only calls needing real Cloudflare/Atlassian creds will fail.

## Phase 2 — KEDA autoscaling

```bash
# Install KEDA once
helm repo add kedacore https://kedacore.github.io/charts && helm repo update
helm install keda kedacore/keda -n keda --create-namespace

# Apply the ScaledObject + drive load
kubectl apply -f deploy/k8s/keda/scaledobject-eval-engine.yaml
kubectl apply -f deploy/k8s/load/load-generator.yaml

# Watch eval-engine scale out, then back to 1 when the load stops
kubectl -n sentinel get scaledobject,hpa,pods -w
```

## Phase 3 — Helm
See `deploy/helm/sentinel/` — `helm install sentinel deploy/helm/sentinel -n sentinel --create-namespace`.
Enable the metrics scrape config (Phase 4) with `--set monitoring.enabled=true` once
kube-prometheus-stack is installed.

## Phase 4 — Observability (Prometheus + Grafana)
The three FastAPI services expose `GET /metrics`; `kube-prometheus-stack` scrapes them and a
pre-built Grafana dashboard shows KEDA scaling, per-pod CPU/mem, request rate, p95 latency,
and restart recovery. See **`deploy/observability/README.md`**.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts && helm repo update
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f deploy/observability/kube-prometheus-stack.values.yaml
kubectl apply -f deploy/observability/servicemonitor.yaml -f deploy/observability/grafana-dashboard-sentinel.yaml
```

## Phase 5 — Chaos engineering
Prove reliability: kill pods / stress CPU / add latency and watch the system self-heal and
KEDA scale. Scripted (`kubectl`-only) or via Chaos Mesh. See **`deploy/chaos/README.md`**.

```bash
bash deploy/chaos/steady-state.sh        # terminal A: availability probe
bash deploy/chaos/pod-kill.sh            # terminal B: kill eval-engine pods, watch recovery
```

## Notes
- Storage is `emptyDir` (ephemeral) — fine for a demo; swap for PVCs to persist.
- `configmap.yaml` / `secret.yaml` are **gitignored**; only the `*.example.yaml` templates are committed.
- `make test` / `make check` are unaffected — nothing here touches package source.
