# Chaos Engineering — proving Sentinel is reliable & scalable

Chaos experiments validate the **steady-state hypothesis**: *Sentinel keeps serving while
pods die, the network slows, or CPU spikes.* Two paths are provided:

1. **Scripted (no install)** — `pod-kill.sh` + `steady-state.sh`. Pure `kubectl`; works on
   any cluster immediately. Best for the demo.
2. **Chaos Mesh (real tool)** — declarative `PodChaos` / `NetworkChaos` / `StressChaos`
   experiments under `chaosmesh/`. More faithful (network latency, CPU stress) but needs
   the Chaos Mesh controller installed.

All experiments target the `sentinel` namespace and are self-contained under `deploy/chaos/`.

## Prereq for a clean result: give it replicas to absorb the hit
A single replica can't survive its own pod being killed without a brief gap. Either:
```bash
kubectl -n sentinel scale deploy/eval-engine --replicas=3       # static headroom
# …or drive load so KEDA scales it out first:
kubectl apply -f deploy/k8s/load/load-generator.yaml
```
With KEDA's `minReplicaCount: 1`, a kill with no headroom still demonstrates **self-healing**
(the pod returns in seconds) — just not zero-downtime.

## Path 1 — scripted (recommended for the demo)

Two terminals:

```bash
# Terminal A — hold the steady-state hypothesis (availability should stay ~100%)
bash deploy/chaos/steady-state.sh                 # probes eval-engine /health for 120s

# Terminal B — inject failure
bash deploy/chaos/pod-kill.sh eval-engine 5 15    # kill a random pod 5x, every 15s
```

Watch recovery:
```bash
kubectl -n sentinel get pods -w                   # killed pods → ContainerCreating → Running
```

**Expected:** `steady-state.sh` ends with `availability: ~100%` (with headroom) and the
Deployment continuously reconciles back to the desired replica count. In Grafana the
"Container restarts (chaos recovery)" panel ticks up while "Running pods" holds steady.

## Path 2 — Chaos Mesh (faithful network/CPU faults)

Install once:
```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org && helm repo update
helm install chaos-mesh chaos-mesh/chaos-mesh \
  -n chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
# (Minikube default runtime is containerd; check `minikube ssh -- 'ls /run/containerd'`.)
```

Run an experiment:
```bash
kubectl apply -f deploy/chaos/chaosmesh/pod-kill.yaml       # recurring pod kills (Schedule)
kubectl apply -f deploy/chaos/chaosmesh/network-delay.yaml  # +200ms latency for 2m
kubectl apply -f deploy/chaos/chaosmesh/cpu-stress.yaml     # CPU stress → triggers KEDA scale-out
kubectl delete -f deploy/chaos/chaosmesh/                   # stop all
```

| Experiment | What it injects | What it proves |
|---|---|---|
| `pod-kill.yaml` | kills one eval-engine pod every 30s | self-healing (Deployment recreates pods) |
| `network-delay.yaml` | 200ms±50ms latency for 2m | latency tolerance — p95 rises then recovers (Grafana panel 6) |
| `cpu-stress.yaml` | 80% CPU load for 3m | **scalability under chaos** — KEDA scales 1→N, then back to 1 |

## How this maps to the hackathon brief
- **§1.6 scalability mindset** — `cpu-stress.yaml` (and the load generator) drive KEDA to
  scale horizontally; the Grafana "replicas" panel shows it.
- **Reliability** — `pod-kill` + steady-state probe show the platform absorbs failure with
  no sustained downtime; the UC2 flight recorder additionally guarantees deterministic
  replay, so a run can be reproduced exactly even after a crash.

## Notes
- Nothing here changes app code or the VM deployment — it only acts on the cluster at runtime.
- Pair with `deploy/observability/` (Prometheus + Grafana) to *see* the impact; without it,
  use `kubectl -n sentinel get pods,hpa -w`.
