// k6 load test for the Sentinel eval engine — drives KEDA scale-out AND measures it.
//
// A ramping-VU profile pushes throughput up so the eval-engine CPU crosses the
// ScaledObject's 50% target (replicas scale 1 -> up to 5), then ramps back to 0 so
// you also see scale-IN. Unlike the curl flood, k6 reports throughput, latency
// percentiles, and PASS/FAIL against the thresholds below.
//
// Tunable via env (set on the Job):
//   TARGET   default http://eval-engine:8000/health  (offline-safe; no CF/secret needed)
//   PEAK_VUS default 200
import http from "k6/http";
import { check } from "k6";

const TARGET = __ENV.TARGET || "http://eval-engine:8000/health";
const PEAK_VUS = Number(__ENV.PEAK_VUS || 200);

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: Math.ceil(PEAK_VUS / 4) }, // warm up
        { duration: "60s", target: PEAK_VUS },                // sustained peak -> KEDA scales out
        { duration: "30s", target: 0 },                       // ramp down -> KEDA scales in
      ],
      gracefulRampDown: "10s",
    },
  },
  // SLOs: the run FAILS (non-zero exit) if these are breached.
  thresholds: {
    http_req_failed: ["rate<0.01"], // < 1% errors even while pods are scaling
    http_req_duration: ["p(95)<500"], // p95 latency under 500ms
  },
};

export default function () {
  const res = http.get(TARGET);
  check(res, { "status is 200": (r) => r.status === 200 });
}
