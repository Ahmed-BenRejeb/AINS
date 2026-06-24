# Sentinel — Scalability & Reliability Evidence

> Deck-ready facts and **exact measured values**. Numbers marked _(measured)_ were
> captured live on the Minikube + KEDA cluster on **2026-06-24**; the rest are design
> facts. Reproduce the measured runs with `deploy/k8s/load/k6/` and `deploy/chaos/`.

---

## 1. Scalability — measured load test (k6) _(measured)_

Ramping-VU load test (`deploy/k8s/load/k6/script.js`) against the live eval engine while
KEDA autoscaled it.

| Metric | Value |
|---|---|
| Total requests served | **153,833** |
| Throughput | **1,281.9 req/s** (~1,282) |
| Failed requests | **0 (0.00%)** |
| Checks passed | **100.00%** (153,833 / 153,833 → HTTP 200) |
| p95 latency | **189.55 ms** |
| p90 latency | 155.55 ms |
| Median latency | 64.03 ms |
| Average latency | 72.59 ms |
| Max latency | 639 ms |
| Peak concurrency | **200 virtual users** |
| Test duration | 2m 00s |
| Data received / sent | 22 MB / 14 MB |
| SLO `p95 < 500 ms` | **PASS** (190 ms) |
| SLO `errors < 1%` | **PASS** (0%) |

**One-liner:** *Sustained 1,282 req/s at 190 ms p95 with 0% errors at 200 concurrent users — while autoscaling.*

## 2. Scalability — autoscaling (KEDA) _(measured + config)_

| Fact | Value |
|---|---|
| Autoscaler | KEDA `ScaledObject` → HPA `keda-hpa-eval-engine` |
| Trigger | CPU utilization |
| Target | **50%** CPU |
| Observed scale-out | **`cpu: 43%/50%`**, replicas **1 → 3** (live) |
| Min / Max replicas | **1 / 5** |
| Polling interval | 15 s |
| Cooldown (scale-in) | 60 s |
| Per-pod CPU request / limit | 100m / 500m |
| Per-pod memory request / limit | 256Mi / 512Mi |
| Direction | Bidirectional (out under load, back to 1 after cooldown) |

**One-liner:** *KEDA scales the eval engine 1→5 on CPU; elastic both ways.*

## 3. Scalability — architecture enablers (design)

- Stateless FastAPI services → horizontally scalable, no session affinity.
- One container image runs all 3 services (shared `uv` workspace) → small, uniform builds.
- Service-to-service via Kubernetes Service DNS, all URLs env-overridable → same code on 1 VM or N pods.
- Dedicated `sentinel` namespace → isolated, multi-tenant-ready.
- Helm-packaged → reproducible deploy; values toggle replicas / KEDA / monitoring.
- Pluggable trigger → CPU today; KEDA also supports Prometheus request-rate, queue depth, HTTP in-flight.
- Stateful deps (xqdrant, MinIO) separated from the scalable compute tier.

## 4. Reliability — chaos / resilience _(measured)_

Steady-state probe held while `deploy/chaos/pod-kill.sh` killed eval-engine pods.

| Metric | Value |
|---|---|
| Availability during chaos | **100.00%** |
| Steady-state probe | **228 OK / 0 fail** |
| Pods killed | **5** eval-engine pods, one every 10 s |
| Downtime | **0** (≥2 replicas always Ready) |
| Recovery | Automatic — `Terminating → Running`, settled to 3 Running |
| Mechanism | Deployment reconciliation + readiness-gated traffic |

**One-liner:** *Killed 5 pods mid-traffic → 100% availability, zero downtime, automatic self-healing.*

## 5. Reliability — platform-level guarantees (design)

- **Deterministic replay (UC2):** every run replays from tape with **0 live LLM calls** — exact reproduction after any crash.
- **Tamper-evident audit:** hash-chained, HMAC-signed receipt per step (write-ahead).
- **Graceful degradation:** tracing, eval-filing, and recording are all best-effort — an outage never fails the request.
- **Upstream-failure handling:** CF Workers AI 429/5xx → retry+backoff (429→30s×3, 5xx→5s×2); exhausted quota → clean **503**, never a hung 500.
- **Reliability metric built in:** `pass^k` (k=8) — *all* k trials must pass (τ-bench standard), not pass@1.
- **Evaluator trustworthiness:** position-bias calibration + Cohen's κ (chance-corrected judge-vs-human agreement).
- **Drift detection:** pass-rate + per-dimension + semantic-centroid drift between windows.
- _Eval-suite figure (label as τ-bench-style consistency gap, not the K8s session): pass@1 100% / pass^8 33.3%._

## 6. Observability — what's instrumented

| Layer | Metrics |
|---|---|
| App `/metrics` (all 3 services) | `http_requests_total`, `http_request_duration_seconds` (p50/p95/p99), `http_requests_in_progress`, request/response sizes |
| Container (cAdvisor) | `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` |
| Cluster (kube-state-metrics) | `kube_deployment_status_replicas`, `kube_horizontalpodautoscaler_status_{current,desired}_replicas`, `kube_pod_status_phase`, `kube_pod_container_status_restarts_total` |
| Stack | Prometheus + Grafana (kube-prometheus-stack), **3 ServiceMonitors**, **7-panel** Sentinel dashboard |
| Tracing | Langfuse — every LLM call + vector search traced |

## 7. Engineering quality (credibility)

- **167 Python tests pass**; mypy `--strict` + ruff clean across all packages.
- **Helm lint clean**; chart renders deterministically.
- Scalability/observability work touched **0 app run-paths** (additive only).
- Chaos tooling: scripted (`pod-kill`, `steady-state`) **+** Chaos Mesh (`pod-kill`, `network-delay`, `cpu-stress`).

---

## Reproduce the measured numbers

```bash
# §1 — k6 load test (scalability)
kubectl -n sentinel create configmap k6-script \
  --from-file=deploy/k8s/load/k6/script.js --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deploy/k8s/load/k6/k6-job.yaml
kubectl -n sentinel logs job/k6-load -f

# §2 — watch KEDA scale during the load
watch -n2 kubectl -n sentinel get hpa,scaledobject,pods

# §4 — chaos / reliability
bash deploy/chaos/steady-state.sh        # terminal A: availability probe
bash deploy/chaos/pod-kill.sh eval-engine 5 10   # terminal B: kill pods
```

**Suggested slide split:** §1 + §2 + §4 as the big bold numbers (measured proof); §3 + §5
as supporting "why it scales / why it's reliable" bullets; §6 + §7 as a credibility footer.
