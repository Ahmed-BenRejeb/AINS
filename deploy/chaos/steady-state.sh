#!/usr/bin/env bash
# Steady-state hypothesis probe (chaos engineering).
#
# Continuously probes a Service from INSIDE the cluster and reports availability.
# Run this in one terminal while you inject failure (deploy/chaos/pod-kill.sh) in
# another: if the system is reliable, availability stays ~100% (the Deployment +
# readiness probes + multiple replicas absorb the kills).
#
#   bash deploy/chaos/steady-state.sh                                  # eval-engine /health, 120s
#   bash deploy/chaos/steady-state.sh http://dashboard:3001/ 180      # custom target + duration
#
# Tip: to prove ZERO downtime, scale the target to >=2 replicas first (or drive load
# so KEDA scales it out) — with a single replica a kill shows a few seconds of recovery.
set -euo pipefail

NS="${NS:-sentinel}"
TARGET="${1:-http://eval-engine:8000/health}"
DURATION="${2:-120}"

echo "steady-state probe: $TARGET for ${DURATION}s (every 0.5s) — inject chaos now"
kubectl -n "$NS" run "steady-state-$$" --rm -i --restart=Never \
  --image=curlimages/curl:8.10.1 --quiet -- \
  sh -c '
    ok=0; fail=0; end=$(( $(date +%s) + '"$DURATION"' ));
    while [ "$(date +%s)" -lt "$end" ]; do
      if curl -fsS -m 2 -o /dev/null "'"$TARGET"'"; then
        ok=$((ok+1));
      else
        fail=$((fail+1)); echo "  DOWN at $(date +%T)";
      fi
      sleep 0.5;
    done
    total=$((ok+fail)); [ "$total" -eq 0 ] && total=1;
    echo "----------------------------------------";
    echo "steady-state: ok=$ok fail=$fail";
    awk "BEGIN{printf \"availability: %.2f%%\n\", ($ok/$total)*100}"
  '
