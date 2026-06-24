# Observability — Prometheus + Grafana (kube-prometheus-stack)

Gives the Sentinel cluster a full metrics stack so the **scalability** (KEDA replica
scaling, per-pod CPU/mem) and **reliability** (request rate, p95 latency, restart
recovery) story is *visible*, not just asserted. Self-contained under `deploy/observability/`
— it does not change how the app runs on the VM.

## What's here
| File | Purpose |
|---|---|
| `kube-prometheus-stack.values.yaml` | Minikube-tuned Helm values (Prometheus + Grafana + Alertmanager + node-exporter + kube-state-metrics) |
| `servicemonitor.yaml` | Tells Prometheus to scrape `/metrics` on eval-engine, flight-recorder, atlassian-remote |
| `grafana-dashboard-sentinel.yaml` | Auto-imported Grafana dashboard (replicas, CPU/mem, req rate, p95, restarts) |

The three FastAPI services expose Prometheus metrics at **`GET /metrics`** via
`prometheus-fastapi-instrumentator` (wired in `packages/*/api.py`) — request counts,
latency histograms, and in-progress gauges per endpoint. The endpoint is unauthenticated
(like `/health`) because the services are internal-only ClusterIPs.

## Install (once)

```bash
# 1. Install the stack into its own namespace
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f deploy/observability/kube-prometheus-stack.values.yaml

kubectl -n monitoring get pods -w        # wait for Prometheus + Grafana Running

# 2. Point Prometheus at the Sentinel services + load the dashboard
kubectl apply -f deploy/observability/servicemonitor.yaml
kubectl apply -f deploy/observability/grafana-dashboard-sentinel.yaml
```

> The Sentinel stack (`kubectl apply -k deploy/k8s`) must already be running in the
> `sentinel` namespace — the ServiceMonitors select those Services.

## Open Grafana

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
# browse http://localhost:3000  → user: admin  pass: sentinel
# Dashboards → "Sentinel — Reliability & Scalability"
```

Prometheus itself (to confirm targets are UP):

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090
# http://localhost:9090/targets  → eval-engine / flight-recorder / atlassian-remote = UP
```

## Verify scraping works

```bash
# /metrics is live on each service
kubectl -n sentinel port-forward svc/eval-engine 8000:8000 &
curl -s localhost:8000/metrics | grep http_requests_total | head

# Prometheus discovered the ServiceMonitors
kubectl -n monitoring exec -it sts/prometheus-kube-prometheus-stack-prometheus -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/targets' | grep -o '"job":"[^"]*"' | sort -u
```

## What the dashboard proves
| Panel | Metric | Story |
|---|---|---|
| eval-engine replicas | `kube_deployment_status_replicas` + HPA desired | KEDA scales 1→N under load, back to 1 |
| Running pods | `kube_pod_status_phase{phase=Running}` | capacity tracks demand |
| CPU per pod | `container_cpu_usage_seconds_total` | the signal KEDA's CPU trigger reacts to |
| Memory per pod | `container_memory_working_set_bytes` | headroom under load |
| Request rate | `http_requests_total` (app `/metrics`) | throughput per service |
| p95 latency | `http_request_duration_seconds_bucket` | latency stays bounded as replicas grow |
| Container restarts | `kube_pod_container_status_restarts_total` | **chaos recovery** — killed pods come back |

## Run it with load (combine with KEDA + chaos)
```bash
kubectl apply -f deploy/k8s/keda/scaledobject-eval-engine.yaml
kubectl apply -f deploy/k8s/load/load-generator.yaml     # drives CPU up → watch panels 1+3+5 move
bash deploy/chaos/pod-kill.sh eval-engine                # watch panel 7 (restarts) + panel 2 hold steady
```

## Notes
- Tuned for Minikube: control-plane scrape jobs (etcd/scheduler/controller/proxy) are
  disabled in the values file (they don't exist as scrape targets on Minikube).
- No app code path changed for the VM deployment — `/metrics` is additive and
  unauthenticated, the services stay internal-only.
- `make test` / `make check` stay green (the instrumentation is a normal dependency,
  verified: 167 Python tests pass, mypy --strict + ruff clean).
