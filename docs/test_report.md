# Sentinel Test Report — 2026-06-22 (live re-run, CF budget restored)

> Comprehensive system test + fixes. Run on the Azure VM (`48.220.48.34`) against
> the live deployed stack. Author: Claude Code (Opus 4.8) at the request of Ahmed Saad.
>
> **Headline:** The Cloudflare Workers AI daily budget **cleared on schedule** at
> ~15:00 UTC (24h after the prior day's run — confirming the rolling-window theory),
> so the whole pipeline was exercised **live**. All three previously-reported issues
> are **fixed and verified end-to-end with real LLM calls**: `/search` returns 200,
> runbooks now retrieve and are cited in RCAs, and Langfuse captured fresh traces
> (53 → 87). A full 5-incident `/analyze` loop ran green (real RCA + eval verdict +
> replay link for each), with cassettes, D1 manifests, and D1 trace rows all
> confirmed. One **new gap was found and fixed**: eval verdicts were never persisted
> to the D1 `eval_verdicts` table (the table existed but nothing wrote to it) — now
> persisted best-effort, with a row verified live.
>
> **Update (~17:30 UTC) — model finalized + first real pass^k.** The free CF budget
> is genuinely ~10k neurons/day and is easily consumed by one full test pass, so two
> changes were made to keep testing today: (1) the main RCA + judge model was moved
> off Llama 3.3 70B — first to Gemma, but **Gemma proved unfit** (`gemma-3-12b` is
> `410 Gone`; the only available Gemma, `gemma-4-26b-a4b`, is a reasoning model that
> returns `content: null` with the answer in `message.reasoning`) — and finalized to
> **`@cf/meta/llama-3.1-8b-instruct-fp8-fast`** (~6× cheaper output, clean JSON, fast
> for Forge's 25s); the response parser was hardened to handle all three CF response
> shapes. (2) Workers AI was routed to a **teammate's CF account** via a new
> `CF_AI_ACCOUNT_ID`/`CF_AI_API_TOKEN` split (D1 stays on the primary account). On
> that budget the **full 5-incident E2E re-ran green** and a **real `pass^k` sweep
> completed for the first time**: **pass@1 100% / pass^8 33.3%** (see below) — the
> headline τ-bench reliability result. The earlier-in-the-day run (Llama 3.3 70B,
> primary account) is preserved below for the record; numbers there reflect that run.

---

## Data Audit (pre-test state)

Captured at the start of the session (before any change). All values are live reads.

### Services (systemd) + health

| Service | Unit | Port | `/health` | env loaded |
|---|---|---|---|---|
| Eval Engine (UC1) | `sentinel-eval` | 8000 | `{"status":"ok"}` | ✓ |
| Flight Recorder (UC2) | `sentinel-flight` | 8001 | `{"status":"ok"}` | ✓ |
| Atlassian Remote (UC3) | `sentinel-remote` | 8080 | `{"status":"ok"}` | ✓ |
| Dashboard | `sentinel-dashboard` | 3001 | active | ✓ |
| Cloudflare Tunnel | `cloudflared` | — | active | — |

`/srv/sentinel/.env` carries the CF / D1 / Atlassian / Langfuse / MinIO / Forge /
HMAC keys. `XQDRANT_*`, `VECTOR_SIMILARITY_THRESHOLD`, `RUNBOOK_SIMILARITY_THRESHOLD`,
`EVAL_ENGINE_URL`, `FLIGHT_RECORDER_URL` are **not** in `.env` — they resolve from
code defaults (relevant to Issue 2).

### xqdrant (`localhost:6333`)

| Collection | Points | Sample payloads |
|---|---|---|
| `incidents` | **101** | `AO-7` "DB connection refused — max connections exceeded"; `AO-49` "Crypto mining process detected — high CPU" (fields: `source_id`, `title`, `text`, `category`, `source_type`) |
| `runbooks` | **11** | `Runbook: High CPU Utilization`; `Runbook: Database Connection Pool Exhaustion` (all share the same templated Overview/Detection/Diagnosis/Remediation skeleton) |

### Cloudflare D1 (`sentinel-traces`) — pre-test

| Table | Rows (pre) | Rows (post-test) |
|---|---|---|
| `run_manifests` | **13** | 20 |
| `trace_records` | **42** | 61 |
| `eval_verdicts` | **0** | **1** (after the persistence fix; see below) |

### MinIO (`sentinel-cassettes`)

**14** cassette objects pre-test → **21** post-test, `~50–55 KB` each, keyed by
`run_id` (uuid4 hex).

### Atlassian (`AO` project)

**103** issues — the seeded 100 incidents plus auto-filed eval verdict issues
(e.g. `AO-104` "Sentinel eval uncertain: 75d5ca5e (trial 0)").

### Langfuse (`http://127.0.0.1:3000`, project **AINS**)

Health `{"status":"OK","version":"3.188.0"}`; all 6 containers up. **53 traces**
pre-test (all from a single window on 2026-06-21 14:05) → **87 traces** post-test
(fresh `xqdrant-search` / `rca-generation` / `llm-judge` spans from this session's
live calls).

---

## Service Health

All three Python services `active (running)` under systemd, all `/health` → 200,
env loaded from `EnvironmentFile=/srv/sentinel/.env`. After pulling the new drift
feature from `origin/main` (`6ee8eb5` `feat(uc1): behavioural drift detection`), the
services were `uv sync`'d and restarted to load the latest code. Dependencies
(xqdrant, MinIO, D1, Atlassian, Langfuse, CF Workers AI) all reachable.

**Cloudflare Workers AI budget timeline (this session):**

```
~01:41 UTC  embed/chat/safety → 429 code 4006 (blocked, prior day's spend)
~15:20 UTC  embed → HTTP 200, chat → HTTP 200   (budget CLEARED — rolling window)
15:24–15:44 live E2E (7×/analyze) + k=8 eval sweep  (consumes the day's budget)
~15:44 UTC  embed → 429 code 4006 again          (re-exhausted by this test pass)
```

This is direct confirmation of the rolling-window model: the budget cleared ~24h
after the previous run and was then fully consumed by one comprehensive test pass.

---

## Issue 1: `/search` endpoint (was 500 / hang)

**Root cause:** `/search` embeds the query via `cf_ai_client.cf_ai_embed`; when CF
returned the daily-quota **429 (code 4006)**, the retry policy treated it as
transient → `asyncio.sleep(30)` × 3 = **90 s** of pointless backoff, then a
re-raised `httpx.HTTPStatusError` surfaced as a bare **500** past the client timeout.

**Fix (committed previously, verified this session):**
- `cf_ai_client._post` **fails fast** on the daily-quota 429 (detects code 4006 /
  "daily free allocation" / "neurons") — no backoff.
- `api.py` maps any upstream `httpx.HTTPStatusError` to a clean **503**.

**Live verification (CF available):**

```
POST /search {"query":"database connection pool exhausted","index":"incidents"}
→ HTTP 200 in 4.27 s — 3 hits, scores 0.856 / 0.833 / 0.811
POST /search {"index":"runbooks", same query}
→ HTTP 200 in 1.39 s — 3 hits, top 0.785 (Database Connection Pool Exhaustion)
```

**Quota-path verification (CF exhausted):** `/search` → **503 in 0.11 s** with
`"… rate limit or daily neuron allocation exhausted; retry later"` (no hang).
Both behaviours are now correct. Regression tests:
`test_post_fails_fast_on_daily_quota_429`, `test_search_maps_upstream_cf_429_to_503`.

---

## Issue 2: Runbook retrieval (was always 0 hits)

**Root cause — two parts:**
1. **The active threshold was 0.75, not 0.60.** The constant was imported from
   `trace_core.VECTOR_SIMILARITY_THRESHOLD` (hard-wired 0.75), so the `.env` knob was
   never read. Incident → runbook cosine tops out at ~0.71–0.79 (and via the full
   incident text, lower), so every runbook fell under the 0.75 floor.
2. **Generic runbook content.** All 11 runbooks share one boilerplate template,
   compressing the score range (the title carries most of the discriminating signal).

**Fix (committed previously, verified this session):** per-collection floors in
`atlassian_remote.config` — incidents use `VECTOR_SIMILARITY_THRESHOLD` (0.75),
runbooks use `RUNBOOK_SIMILARITY_THRESHOLD` (**0.60**, env-overridable);
`search_similar(threshold=…)` resolves per collection.

**Live verification:** `/search index=runbooks` returns hits with scores
**0.785 / 0.643 / 0.624** — the two below 0.75 would have been dropped under the old
floor and are now correctly kept. In the full `/analyze` flow, **every one of the 5
E2E incidents returned runbooks** (1–5 each) and the RCA `evidence` now **cites
them** — e.g. AO-11: *"Relevant runbook [06ee8960…] with score 0.72"*. The exact
symptom (RCAs citing zero runbooks) is gone. Regression tests:
`test_runbooks_use_lower_threshold_than_incidents`,
`test_explicit_threshold_overrides_per_collection_default`.

---

## Issue 3: Langfuse tracing

**Diagnosis — tracing works; the prior "empty" was CF-outage staleness.** With CF
restored, fresh traces landed in real time. Trace count went **53 → 87** during this
session; the most recent spans (15:26–15:39 UTC) are exactly the expected shape per
`/analyze`: **2× `xqdrant-search`** (incidents + runbooks) + **1× `rca-generation`**
+ **2× `llm-judge`** (the calibrated judge runs twice for position-bias detection).
Each trace has its observation populated. Delivery is to
`LANGFUSE_HOST_INTERNAL=http://127.0.0.1:3000`, project **AINS**; `/api/public/health`
→ `OK`; both `langfuse-web` / `langfuse-worker` healthy.

A previously-fixed defect (orphan `xqdrant-search` span when the embed call raised)
also has its regression test (`test_span_is_ended_when_embed_fails`).

---

## New issue found & fixed: eval verdicts not persisted to D1

**Finding:** the D1 `eval_verdicts` table exists in `infra/cloudflare/d1-schema.sql`
(with three indexes) but **no code ever wrote to it** — `eval_verdicts` held 0 rows.
The reporter returned the verdict inline and filed a Jira issue, but the durable
record the dashboard's verdict screens are meant to read was never created.

**Fix:** new `eval_engine/verdict_store.py` — a best-effort D1 writer that mirrors
the flight recorder's `storage.d1_client` write side (the same way `cassette_store`
mirrors its MinIO side, so eval-engine takes no new cross-package dependency). It
flattens an `EvalVerdict` onto the schema columns (overall_score = mean dimension
score, attribution step/component, dimensions JSON, etc.), no-ops when D1 env is
unset, and swallows/logs any error so evaluation never fails. Wired into
`reporter.evaluate_run` after the verdict is assembled.

**Live verification:** after restarting `sentinel-eval`, a fresh `/analyze` (AO-31)
wrote a row — `eval_verdicts` went **0 → 1**: `verdict=pass, overall_score=0.8625,
confidence=0.825, flag_for_human=0`. 4 regression tests added
(`tests/test_verdict_store.py`): row mapping, no-op when unconfigured, INSERT when
configured, error-swallowing.

---

## End-to-End Test Results (5 incidents, live)

`POST /analyze` on the 5 target incidents, spaced 10 s apart. **All returned HTTP
200** with a full envelope (`run_id`, `rca_draft`, `similar`, `runbooks`,
`flag_for_human`, `eval_verdict`, `replay_link`).

| Incident | run_id (hex) | similar | runbook | RCA conf / severity | eval verdict | judge conf |
|---|---|---|---|---|---|---|
| AO-11 | `816cf0e4…` | 5 (0.99–0.76) | **5** (0.72–0.61) | 0.95 / critical | **uncertain** (position-bias flag) | 0.50 |
| AO-21 | `434ed462…` | 2 (1.00, 0.75) | **5** (0.68–0.62) | 0.90 / critical | **fail** | 1.00 |
| AO-51 | `b7513f88…` | 2 (1.00, 0.79) | **5** (0.70–0.62) | 0.90 / high | **pass** | 0.89 |
| AO-71 | `2714289b…` | 1 (1.00) | **2** (0.63, 0.62) | 0.80 / high | **pass** | 0.83 |
| AO-91 | `621b8784…` | 2 (0.99, 0.75) | **1** (0.65) | 0.90 / high | **pass** | 0.83 |

Diverse verdicts (pass / fail / uncertain) demonstrate the grader pipeline and the
position-bias calibration (AO-11 flipped → `uncertain` + flag-for-human). **Every
incident retrieved runbooks** (Issue 2 fixed in the real flow).

### Storage confirmation (per run_id)

| Check | Result |
|---|---|
| MinIO cassette per run_id | **5/5 FOUND** (bucket 14 → 21 objects) |
| D1 `run_manifests` row | **5/5 present** (13 → 19, +AO-31 → 20) |
| D1 `trace_records` | **+19** (42 → 61) |
| D1 `eval_verdicts` row | written for AO-31 (0 → 1) after the persistence fix; the 5 E2E runs predate the eval-engine restart so were not persisted |
| Langfuse trace per run | **confirmed** — fresh `rca-generation` / `xqdrant-search` / `llm-judge` spans at 15:26–15:39 UTC |

> Note: the 5-incident loop ran before the eval-engine was restarted with the new
> `verdict_store`, so their verdicts were returned inline (and filed as Jira issues)
> but not written to D1. AO-31, run after the restart, proves the persistence path.

---

## pass^k Results (from `make eval`)

> **Update — this is now a REAL result.** After switching the main model to
> `llama-3.1-8b-fp8-fast` and routing Workers AI to a teammate's CF account (the
> `CF_AI_*` split), the `pass^k` sweep actually completed for the first time.

`make eval` runs `scripts/run_synthetic_eval.py --k 8` (the two non-CF script bugs
fixed earlier — the `["runs"]` access on a bare-array response and the hard
`dotenv` import — stay fixed). This run used `--limit 4` to stay inside the
teammate budget; 3 of the 4 runs scored fully (k=8 trials each) before the 4th hit
a 503 as the budget ran low:

```
=== Sentinel Eval Suite (k=8) ===
[1/4] 12a8129d... ✓ pass^8=True  consistency=100%
[2/4] e6bdbaf4... ✗ pass^8=False consistency=50%
[3/4] 09168e1a... ✗ pass^8=False consistency=62%
[4/4] e6a6c3ff... ERROR: 503 (teammate budget ran low)
=== Summary ===  pass@1: 100.0%   pass^8: 33.3%   consistency: 70.8%
```

| Metric | Value |
|---|---|
| **pass@1** (≥1 of k trials passed) | **100.0%** |
| **pass^8** (ALL 8 trials passed) | **33.3%** (1 of 3 fully-scored tasks) |
| Consistency rate (avg passing trials) | 70.8% |
| Tasks fully scored / trials | 3 / 24 |

Per-dimension (mean / pass-rate ≥0.7): **Correctness 0.90 / 95.7%**, Safety 0.92 /
91.7%, Reasoning 0.78 / 95.7%, Efficiency 0.64 / 60.9%.

**This is the headline τ-bench result the whole project is built around:** pass@1 is
a perfect 100%, but pass^8 collapses to **33%** — i.e. every task passes *some* run,
yet only 1 of 3 passes *all 8* trials. That is exactly the "catastrophic
inconsistency that pass@1 hides" (τ-bench, arXiv:2406.12045) that the platform
exists to surface. `docs/eval_report.md` now holds these real numbers (no longer a
template). A larger sweep (more tasks) just needs more budget; the 8B judge is
noisier than the 70B, which is itself part of why consistency drops.

---

## Tests & Checks

- **144 Python tests pass** (130 prior baseline + 10 from the pulled drift feature +
  **4 new** `verdict_store` tests). `eval-engine` ruff + `mypy --strict` clean;
  `check-docs` clean.
- New this session: `packages/eval-engine/src/eval_engine/verdict_store.py` +
  `tests/test_verdict_store.py` (4 tests); conftest now unsets `CF_D1_DATABASE_ID`
  so the D1 persist deterministically no-ops in tests (no network).
- `make check` (repo-wide lint) still fails **only** on the **pre-existing**
  `scripts/seed_atlassian.py` + `scripts/run_synthetic_eval.py` lint errors —
  unchanged by this work; the per-package gates are green.

---

## Recommendations (before demo)

1. **Reserve CF budget for the demo.** The free ~10k neurons/day is consumed by a
   single full test pass. Either move to the Workers **Paid** plan, or (a) do not run
   `make eval` / bulk `/analyze` on demo day, and (b) **pre-record cassettes** and
   demo the deterministic `/replay` path (zero neurons). The budget clears on a
   rolling ~24h window, so a heavy run today blocks live calls until ~the same time
   tomorrow.
2. **Re-seed richer runbook content.** The 0.60 floor makes retrieval work, but the
   boilerplate runbooks cap incident→runbook cosine at ~0.71. Distinct remediation
   content would lift scores and let the floor rise toward incident parity.
3. ~~**Add `GET /verdicts` to eval-engine.**~~ **RESOLVED.** `GET /verdicts` and
   `GET /verdicts/{run_id}` are now live (reading D1 `eval_verdicts`); the dashboard
   verdict screens serve live data when a verdict is persisted.
4. **Authenticate the public APIs** (open §13 TODO). `eval-engine` (:8000) and
   `flight-recorder` (:8001) still have no auth; `/evaluate` defaults to filing a
   Jira issue. Add the `X-Sentinel-Secret` `Depends` that `atlassian-remote` uses.
5. ~~**Forge deploy** remains the only major outstanding item for UC3~~. **RESOLVED.**
   Forge app v2.2.0 is deployed and installed on Jira + Confluence at
   ahmedains.atlassian.net (status Up-to-date).

---

_Generated 2026-06-22 by Claude Code (Opus 4.8) on a live re-run after the CF budget
cleared. All fixes have regression tests; services synced to latest `origin/main`,
restarted, and healthy with the fixes live._
