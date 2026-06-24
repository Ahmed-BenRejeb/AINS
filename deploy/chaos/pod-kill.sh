#!/usr/bin/env bash
# Pod-kill chaos experiment (scripted — no extra cluster tooling required).
#
# Repeatedly deletes a random running pod of a Deployment to prove the system
# self-heals: Kubernetes recreates the pod, readiness probes gate traffic, and
# (with >=2 replicas or under KEDA load) the Service never drops a request.
#
#   bash deploy/chaos/pod-kill.sh                      # kill eval-engine 5x every 15s
#   bash deploy/chaos/pod-kill.sh flight-recorder 8 10 # target, kills, interval(s)
#
# Watch recovery in another terminal:
#   kubectl -n sentinel get pods -w
# and availability with:
#   bash deploy/chaos/steady-state.sh
set -euo pipefail

NS="${NS:-sentinel}"
DEPLOY="${1:-eval-engine}"
KILLS="${2:-5}"
INTERVAL="${3:-15}"

echo "chaos: killing $KILLS pod(s) of app=$DEPLOY in ns/$NS every ${INTERVAL}s"
echo "(Ctrl-C to stop early; the Deployment keeps reconciling either way)"

for i in $(seq 1 "$KILLS"); do
  pod="$(kubectl -n "$NS" get pods -l "app=$DEPLOY" \
          -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
          | shuf -n1 || true)"
  if [ -z "${pod:-}" ]; then
    echo "[$(date +%T)] no running pod for app=$DEPLOY yet — waiting"
    sleep "$INTERVAL"; continue
  fi
  echo "[$(date +%T)] kill #$i → $pod"
  kubectl -n "$NS" delete pod "$pod" --grace-period=0 --wait=false >/dev/null
  sleep "$INTERVAL"
done

echo "----------------------------------------"
echo "recovery state for app=$DEPLOY:"
kubectl -n "$NS" get pods -l "app=$DEPLOY" -o wide
