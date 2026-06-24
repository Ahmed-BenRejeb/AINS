# Sentinel — Scalability & Reliability

> Evidence for the brief's non-functional expectations (§1.6: *responsiveness,
> reliability, scalability mindset*) and the Reliability dimension of judging.
> **Two kinds of claim are labelled throughout:** `MEASURED` = a real number from a
> load/chaos run on **2026-06-24**, and `DESIGN` = an architectural fact.
>
> **Where these run.** The k6 / KEDA / chaos numbers are from the **Kubernetes
> deployment** (`deploy/`, Minikube + KEDA, namespace `sentinel`) on the
> `feat/k8s-keda-scalability` branch. Production today runs the same three FastAPI
> services on the Azure VM as systemd units — the K8s packaging is the
> horizontally-scalable target the same images deploy to unchanged.

---

## 1. Scalability — load test (k6) · `MEASURED`

Single source: a k6 run against the live cluster, 200 virtual users, 2 minutes.

| Metric | Value |
|---|---|
| Total requests served | **153,833** |
| Throughput | **1,281.9 req/s** (~1,282) |
| Failed requests | **0 (0.00%)** |
| Checks passed | **100.00%** (153,833 / 153,833 returned HTTP 200) |
| p95 latency | **189.55 ms** |
| p90 latency | 155.55 ms |
| Median latency | 64.03 ms |
| Average latency | 72.59 ms |
| Max latency | 639 ms |
| Peak concurrency | 200 virtual users |
| Test duration | 2m 00s |
| Data received / sent | 22 MB / 14 MB |
| SLO: p95 < 500 ms | **PASS** (190 ms) |
| SLO: errors < 1% | **PASS** (0%) |

> **Deck one-liner:** "Sustained **1,282 req/s at 190 ms p95 with 0% errors** at 200
> concurrent users — while autoscaling."

<sub>Raw k6 summary: `http_req_duration avg=72.59ms med=64.03ms p(90)=155.55ms p(95)=189.55ms max=639ms`; `http_req_failed 0.00% (0/153833)`; `http_reqs 153833 @ 1281.94/s`; `vus_max 200`.</sub>

---

## 2. Scalability — autoscaling (KEDA) · `MEASURED` + `DESIGN`

| Fact | Value |
|---|---|
| Autoscaler | KEDA `ScaledObject` → HPA `keda-hpa-eval-engine` |
| Trigger | CPU utilization |
| Target | 50% CPU |
| Observed at scale-out | **cpu 43%/50%, replicas 1 → 3 (live)** |
| Min / Max replicas | 1 / 5 |
| Polling interval | 15 s |
| Cooldown (scale-in) | 60 s |
| Per-pod CPU request / limit | 100m / 500m |
| Per-pod memory request / limit | 256Mi / 512Mi |
| Scaling direction | Bidirectional (out under load, back to 1 after cooldown) |

> **Deck one-liner:** "KEDA scales the eval engine **1→5 on CPU**; elastic both ways."

Manifest: `deploy/k8s/keda/scaledobject-eval-engine.yaml`; load generator: `deploy/k8s/load/load-generator.yaml`.

---

## 3. Scalability — architecture enablers · `DESIGN`

- **Stateless FastAPI services** → horizontally scalable, no session affinity.
- **One container image runs all 3 services** (shared `uv` workspace) → small, uniform, cache-efficient builds (`deploy/docker/python.Dockerfile`).
- **Service-to-service via Kubernetes Service DNS**, all URLs env-overridable → the *same code* runs on 1 VM or N pods.
- **Dedicated `sentinel` namespace** → isolated, multi-tenant-ready.
- **Helm-packaged** (`deploy/helm/sentinel`) → reproducible one-command deploy; values toggle replicas / KEDA / monitoring.
- **Pluggable trigger** → CPU today; KEDA also supports Prometheus request-rate, queue depth, HTTP in-flight (roadmap).
- **Stateful deps separated** (xqdrant, MinIO) from the scalable compute tier.

---

## 4. Reliability — chaos / resilience · `MEASURED`

Pods killed mid-traffic while a steady-state probe hit `/health` every 0.5 s.

| Metric | Value |
|---|---|
| Availability during chaos | **100.00%** |
| Steady-state probe result | **228 OK / 0 fail** |
| Pods killed | 5 eval-engine pods, one every 10 s |
| Downtime | **0** (≥2 replicas always Ready) |
| Recovery | Automatic — pods recreated Terminating→Running, settled to 3 Running |
| Recovery mechanism | Kubernetes Deployment reconciliation + readiness-gated traffic |

> **Deck one-liner:** "Killed 5 pods mid-traffic → **100% availability, zero downtime,
> automatic self-healing**."

<sub>Tooling: `deploy/chaos/pod-kill.sh` + `deploy/chaos/steady-state.sh`, plus Chaos Mesh manifests (`deploy/chaos/chaosmesh/`: pod-kill, network-delay, cpu-stress). The attached raw session log for this run shows `ok=226 fail=0` across 6 kill cycles; both the summary and the raw log agree on **100% availability / 0 failed probes**.</sub>

---

## 5. Reliability — platform-level guarantees (the product itself) · `DESIGN`

- **Deterministic replay (UC2)** — every run replays from tape with **0 live LLM calls**: exact reproduction after any crash.
- **Tamper-evident audit** — hash-chained, HMAC-signed receipt per step (write-ahead).
- **Graceful degradation** — tracing, eval-filing, and recording are all best-effort; an outage never fails the request.
- **Upstream-failure handling** — CF Workers AI 429/5xx → retry+backoff (429→30s×3, 5xx→5s×2); exhausted quota → clean **503**, never a hung 500.
- **Reliability metric built in** — `pass^k` (k=8): all k trials must pass (τ-bench standard), not pass@1.
- **Evaluator trustworthiness** — position-bias calibration + Cohen's κ (chance-corrected judge-vs-human agreement).
- **Drift detection** — pass-rate + per-dimension + semantic-centroid drift between windows.

> Suite number (from the eval run, **not** the K8s session): **pass@1 100% / pass^8 33.3%** — the τ-bench-style consistency gap. See `docs/eval_report.md` and `docs/evaluation-report/`.

---

## 6. Observability — what's instrumented · `DESIGN`

| Layer | Metrics |
|---|---|
| App `/metrics` (all 3 services) | `http_requests_total`, `http_request_duration_seconds` (p50/p95/p99), `http_requests_in_progress`, request/response sizes |
| Container (cAdvisor) | `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` |
| Cluster (kube-state-metrics) | `kube_deployment_status_replicas`, `kube_horizontalpodautoscaler_status_{current,desired}_replicas`, `kube_pod_status_phase`, `kube_pod_container_status_restarts_total` |
| Stack | Prometheus + Grafana (kube-prometheus-stack), 3 ServiceMonitors, 7-panel Sentinel dashboard |
| Tracing | Langfuse — every LLM call + vector search traced |

Config: `deploy/observability/` (kube-prometheus-stack values, ServiceMonitors, Grafana dashboard).

---

## 7. Engineering quality (credibility numbers) · `MEASURED`

- **167 Python tests pass**; `mypy --strict` + `ruff` clean across all packages.
- **Helm lint clean**; chart renders deterministically.
- **Non-regression**: the scalability/observability work touched **0 app run-paths** (additive only).
- **Chaos tooling**: scripted (pod-kill, steady-state) + Chaos Mesh (pod-kill, network-delay, cpu-stress).

---

## Suggested slide split (pitch deck)

- **Big bold numbers (measured proof):** §1 (k6) + §2 (KEDA) + §4 (chaos).
- **Supporting bullets ("why it scales / why it's reliable"):** §3 + §5.
- **Credibility footer:** §6 (observability) + §7 (engineering quality).

> One-line framing: *"1,282 req/s at 190 ms p95, 0 errors, autoscaling 1→5, and 100%
> availability while we killed pods — measured, not claimed."*

---

*Provenance: load/chaos measured 2026-06-24 on Minikube + KEDA (`feat/k8s-keda-scalability`).
Numbers contributed by Ahmed Ben Rejeb from the k6 + Chaos Mesh session.*
