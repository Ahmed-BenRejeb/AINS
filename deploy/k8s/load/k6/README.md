# k6 load test — measured scalability proof

Turns "CPU went up" into a quantitative result: **sustained throughput at p95 latency
with a pass/fail SLO**, while KEDA scales eval-engine out and back. Use this instead of
(or alongside) the simpler `curl` flood in `../load-generator.yaml` when you want numbers.

## Run it

```bash
# 1. Make the script available to the cluster (one time; re-run if you edit script.js)
kubectl -n sentinel create configmap k6-script \
  --from-file=deploy/k8s/load/k6/script.js \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Start the load test
kubectl apply -f deploy/k8s/load/k6/k6-job.yaml

# 3. Watch it (two terminals)
kubectl -n sentinel logs job/k6-load -f                 # live k6 summary
watch -n2 kubectl -n sentinel get hpa,pods              # eval-engine scales 1 -> N -> 1
```

Re-run: `kubectl -n sentinel delete job k6-load` then re-apply.

## What you get
At the end k6 prints (and the thresholds gate PASS/FAIL):
- `http_reqs` — total requests + **req/s throughput**
- `http_req_duration` — avg / p90 / **p95** / max latency
- `http_req_failed` — error rate (threshold: **< 1%**)
- `iterations`, `vus` — concurrency reached (ramps to `PEAK_VUS`, default 200)

A green run = "we served 200 concurrent users at p95 < 500ms with < 1% errors **while the
platform autoscaled**." That is the scalability headline.

## Tunables (env on the Job)
- `TARGET` — default `http://eval-engine:8000/health` (offline-safe, no Cloudflare/secret).
  Point at `http://eval-engine:8000/evaluate` for the real evaluation path — but that needs
  a POST body + the `X-Sentinel-Secret` header and burns CF Workers AI neurons, so `/health`
  is the right load target for a scaling/reliability demo.
- `PEAK_VUS` — peak concurrent virtual users (default 200). Raise to push more replicas.

## Notes
- `grafana/k6` pulls from docker.io (works here; unlike the ghcr.io/github hosts).
- Pair with `deploy/observability/` Grafana: the *HTTP request rate* and *p95 latency*
  panels move in lockstep with k6's own report — two independent views of the same load.
- Pair with `deploy/chaos/pod-kill.sh` during the k6 run for the "chaos under load" money shot.
