# Sentinel — Validation Guide & Spec Coverage

> **Purpose.** This document lets an enterprise engineer / AI-platform owner validate
> Sentinel end-to-end against the official AINS 2026 brief (`docs/TECHNICAL_SPECS.md`)
> and record structured feedback. It maps every acceptance criterion to a concrete
> test and the live evidence, then gives a step-by-step validation playbook and a
> remarks template.
>
> Last validated: **2026-06-23** on the live VM (`48.220.48.34`), main model
> `@cf/meta/llama-3.1-8b-instruct-fp8-fast`, all services healthy.

---

## 0. The one-sentence claim to validate

> *Remove the AI and the system stops working:* Sentinel **records** an Atlassian
> incident-triage agent's full trajectory (UC2), **evaluates** every run with a
> multi-level grader pipeline that produces auditable verdicts, failure attribution,
> drift and pass^k (UC1), and the agent it instruments is a **real Atlassian
> workflow** that drafts grounded RCAs and resolves semantic duplicates (UC3) — all
> surfaced on a human dashboard.

---

## 1. Spec Coverage Matrix (acceptance criteria → evidence)

Legend: ✅ met & live-verified · 🟦 built, not deployed to Forge cloud.

### UC1 — Continuous Evaluation (§2.4)

| Criterion | Priority | Status | How it's met / how to verify |
|---|---|---|---|
| Trajectory capture works | Must | ✅ | `POST /analyze` tapes the full trace; inspect at `dashboard/runs/{id}` or `GET :8001/runs/{id}` (4 steps: embed → search incidents → search runbooks → RCA). |
| Multi-level evaluation | Must | ✅ | **Three** levels produce distinct signals: deterministic **code grader** (schema/tool-call/loop/token checks), **LLM judge** (calibrated rubric scoring), **safety pre-filter** (Llama Guard). `GET :8000/verdicts/{id}` shows per-dimension scores. |
| Failure attribution | Must | ✅ | `EvalVerdict.failure_attribution` blames a step+component (VeriLA-style DAG attributor). Visible on `dashboard/verdicts/{id}`. |
| Human-readable verdict | Must | ✅ | Every run yields a structured `EvalVerdict` with `recommended_action`, dimensions, self-critique — readable by a non-AI engineer. |
| Drift detection | Should | ✅ | `POST :8000/drift` returns pass-rate + per-dimension + semantic (BGE-centroid) drift. Live: `drift_detected=true`, "pass rate 100% → 0%". |
| Non-determinism addressed | Should | ✅ | **pass^k** (all-k-trials) not pass@1; calibrated judge flips → `uncertain`; re-evaluating the same run yields different verdicts (demonstrable, see §3). |
| Evaluation of the evaluator | Should | ✅ | `POST :8000/evaluator-quality` scores judge-vs-human **Cohen's κ** (chance-corrected) over a gold set. |

### UC2 — Flight Recorder / Deterministic Replay (§3.4)

| Criterion | Priority | Status | How it's met / how to verify |
|---|---|---|---|
| Record functionality works | Must | ✅ | A live `/analyze` records ≥1 LLM call (RCA) + ≥1 tool call (xqdrant search) into a MinIO cassette + hash-chained D1 audit trail. |
| Deterministic replay | Must | ✅ | `POST :8001/replay {run_id}` → `live_call_count: 0`, `diverged: false`. Re-executes from tape, hits **zero** live APIs. |
| State inspection | Must | ✅ | Inspect the exact input/output per step at `dashboard/runs/{id}` (operation-labelled, model id, readable previews). |
| Divergence editing | Should | ✅ (bisect) | `POST :8001/bisect {good,bad}` finds the first diverging step between two runs; surfaced on `dashboard/replay/{id}`. (Full mid-replay prompt-injection is the next step.) |

### UC3 — Atlassian Workflow (§4.4)

| Criterion | Priority | Status | How it's met / how to verify |
|---|---|---|---|
| End-to-end workflow works | Must | ✅ | `POST /analyze {incident_key}` → fetch incident → retrieve similar + runbooks → draft RCA → record → eval → return verdict + replay link. |
| AI necessity verified | Must | ✅ | Core is semantic vector retrieval + LLM RCA synthesis + LLM duplicate judgement — impossible with Jira keyword rules / IF-THEN (see §4). |
| Actionable output produced | Must | ✅ | Structured `RcaDraft` (root cause, evidence, severity, assignee) → ADF Jira comment; verdicts → AO Jira Incidents; duplicates → auto-linked. |
| Evaluation metric defined | Should | ✅ | The RCA agent is itself measured by UC1 (pass^k, dimension scores). `docs/eval_report.md`. |
| Graceful degradation | (Key) | ✅ | `flag_for_human` when confidence < 0.70 (RCA) / < 0.85 (duplicate auto-link); upstream outages → clean 503, never a crash. |

### Bonus (§5.2)

| Bonus | Status | Evidence |
|---|---|---|
| Protocol gap addressed + documented | ✅ | `spec/otel-genai-replay-extension.md` (replay cassette attrs) + `spec/mcp-audit-trail-proposal.md` (hash-chained audit). |
| Self-evaluation | ✅ | `SelfEvaluation` (judge_confidence + self_critique) + position-bias calibration flags low-confidence verdicts for humans. |
| Real enterprise validation | ⬜ | **This document is the harness for it** — run §3, fill in §5. |
| Open contribution | ✅ | The two `spec/*.md` artefacts + `trace-core` shared schema. |

---

## 2. Pre-flight (5 minutes)

All services run on the VM behind a Cloudflare tunnel. A browser passes the bot
challenge; `curl` from a shell gets `403 cf-mitigated` on the **public** hostnames —
that is expected and not an outage. Validate either in a **browser** (public URLs) or
**on the VM** against `127.0.0.1` (shown below).

```bash
# health (on the VM)
for p in 8000 8001 8080 3001; do curl -s localhost:$p/health 2>/dev/null || curl -s localhost:$p/ -o /dev/null -w "dashboard %{http_code}\n"; done
# secret for the UC3 backend
SECRET=$(sudo grep FORGE_REMOTE_SECRET /srv/sentinel/.env | cut -d= -f2)
```

Public URLs (browser): dashboard `https://dashboard.ahmedxsaad.me`, Langfuse
`https://langfuse.ahmedxsaad.me`, Jira `https://ahmedains.atlassian.net` (project AO).

---

## 3. Validation Playbook (run these, record what you see)

### T1 — UC3 end-to-end + UC2 record (the core loop)
```bash
curl -s -X POST localhost:8080/analyze -H "Content-Type: application/json" \
  -H "X-Sentinel-Secret: $SECRET" -d '{"incident_key":"AO-51","requested_by":"validator"}' | jq
```
**Expect:** HTTP 200 in <45s with `run_id`, a structured `rca_draft` (root cause +
evidence citing similar incidents **and** runbooks), `similar`/`runbooks` hits,
`eval_verdict`, and a `replay_link` to the dashboard.
**Remark on:** is the root cause plausible? does it cite real evidence? is severity sane?

### T2 — UC2 deterministic replay (zero live calls)
```bash
curl -s -X POST localhost:8001/replay -H "Content-Type: application/json" \
  -d "{\"run_id\":\"<run_id from T1>\"}" | jq
```
**Expect:** `live_call_count: 0`, `diverged: false`. This proves the run is
reproducible without touching live APIs (the UC2 promise).

### T3 — UC2 trajectory inspection (dashboard)
Open `dashboard/runs/<run_id>`. **Expect:** a 4-step timeline — `embedding` (bge) →
`vector search` incidents → `vector search` runbooks → `llm chat` (llama-3.1-8b) —
each with readable input/output previews, not raw JSON.

### T4 — UC1 verdict + multi-level + attribution + human-readable
Open `dashboard/verdicts/<run_id>` (or `GET :8000/verdicts/<run_id>`).
**Expect:** an overall verdict, **per-dimension** scores (correctness / efficiency /
safety / reasoning_quality), a self-critique, judge confidence, a recommended action,
and (on non-pass) a failure attribution naming the step + component.

### T5 — UC1 non-determinism + pass^k
```bash
# Evaluate the SAME run 3 times as a pass^k batch:
RID=<run_id>; curl -s -X POST localhost:8000/evaluate/batch -H "Content-Type: application/json" \
  -d "{\"run_ids\":[\"$RID\",\"$RID\",\"$RID\"],\"k\":3}" | jq '{pass_hat_k, consistency_rate, verdicts: [.verdicts[].verdict]}'
```
**Expect:** the same run can yield **different** verdicts across trials, and
`pass_hat_k` is 0 unless **all** trials pass — the τ-bench insight that pass@1 hides.
The headline `make eval` run (`docs/eval_report.md`): **pass@1 100% / pass^8 33%**.

### T6 — UC1 drift detection
```bash
# (run on the VM; builds two windows from stored verdicts)
python3 - <<'PY'
import json,urllib.request
v=json.load(urllib.request.urlopen("http://127.0.0.1:8000/verdicts?limit=200"))
b=[x for x in v if x["verdict"]=="pass"][:6]; c=[x for x in v if x["verdict"]!="pass"][:6] or b[:1]
r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/drift",
  data=json.dumps({"baseline":b,"current":c}).encode(),headers={"Content-Type":"application/json"}))
print(json.load(r)["summary"])
PY
```
**Expect:** a human-readable drift summary ("pass rate X% → Y%; largest dimension shift…").

### T7 — UC1 evaluation-of-the-evaluator (Cohen's κ)
`POST :8000/evaluator-quality` with a gold set of `{run_id, records, expected}` cases
→ returns accuracy + **Cohen's κ** + per-label recall (chance-corrected agreement of
the judge vs a human label). Endpoint returns 200; unit-tested in
`tests/test_evaluator_quality.py`.

### T8 — UC3 semantic duplicate resolver
```bash
curl -s -X POST localhost:8080/duplicates -H "Content-Type: application/json" \
  -H "X-Sentinel-Secret: $SECRET" -d '{"incident_key":"AO-11","requested_by":"validator"}' | jq '.verdict, .flag_for_human'
```
**Expect:** `is_duplicate`, a `duplicate_of` target, and a confidence; auto-links only
when confidence ≥ 0.85, else `flag_for_human: true` (graceful degradation).

### T9 — UC2 bisect (divergence triage)
```bash
curl -s -X POST localhost:8001/bisect -H "Content-Type: application/json" \
  -d '{"good_run_id":"<run A>","bad_run_id":"<run B (different incident)>"}' | jq '{identical, first_diverging_step, reason}'
```
**Expect:** two different runs are `identical: false` with a `first_diverging_step`.
(Two runs of the **same** incident are the meaningful comparison; different incidents
diverge at step 0.)

### T10 — Explainability surfaces
Open `dashboard/` (overview): per-task **pass rate**, true **pass^k**, flagged-for-human
count; **Langfuse** (`langfuse.ahmedxsaad.me`): every LLM call / vector search traced;
**Jira AO**: auto-filed eval Incident issues.

---

## 4. "Could this be done without AI?" (the necessity argument)

| Step | Why conventional automation fails |
|---|---|
| Find similar past incidents | Different wording, same root cause — keyword/JQL search misses it; needs 768-dim semantic retrieval. |
| Draft the RCA | Synthesises a hypothesis + evidence + severity from unstructured incident text — not template fill. |
| Duplicate resolution | "DB pool exhausted" vs "cannot connect, pool full" are the same bug in different words — exact-match dedup misses it. |
| Evaluating the agent | The agent is non-deterministic; exact-match unit tests are structurally incompatible — needs an LLM-judge + pass^k. |

---

## 5. Enterprise Remarks Template (please fill in)

| # | Area | Question | Your finding (1–5) | Notes |
|---|---|---|---|---|
| 1 | Output quality | Are the RCAs accurate and actionable on your incidents? | | |
| 2 | Evidence/grounding | Does every output cite real, relevant evidence? | | |
| 3 | Explainability | Could a non-AI on-call engineer act on a verdict unaided? | | |
| 4 | Determinism | Did replay reproduce a run with zero live calls? | | |
| 5 | Reliability | Did anything crash on missing/odd data? (it should 503/flag, not crash) | | |
| 6 | Trust | Does pass^k + drift + κ give you confidence to deploy the agent? | | |
| 7 | Scalability | Concerns at 10× incident volume / concurrent runs? | | |
| 8 | Gaps | What's missing for **your** environment? | | |

**Known limitations to weigh:** (a) UC3 runs as a Forge **Remote** backend +
registered Rovo agent; the final `forge deploy`/`install` to the Atlassian cloud is
the remaining step (the compute + Atlassian read/write are live today). (b) Seeded
runbooks are templated, so incident→runbook cosine tops ~0.71 (handled with a 0.60
runbook floor; richer runbook content would lift it). (c) The judge runs on an 8B
model for cost/speed — noisier than a frontier judge, which is itself visible in the
pass^k gap; swap `CF_AI_MODEL_MAIN` for a larger model to tighten it. (d) Free CF
Workers AI budget is ~10k neurons/day; a full E2E + pass^k sweep can exhaust it (move
to a paid/dedicated key for sustained load).

---

## 6. Scalability note (§1.6)

- **10× data:** retrieval is xqdrant ANN (sub-linear); D1/MinIO are horizontal; the
  per-run cost is bounded (1 embed + 1 RCA + 1 calibrated judge). The bottleneck is
  the LLM neuron budget, addressed by a paid key + the cheap 8B model.
- **Concurrency:** each run is independent and keyed by `run_id`; the recorder's audit
  chain is per-run, so concurrent runs don't contend. Services are stateless FastAPI
  (scale horizontally behind the tunnel).
- **Eval cost:** pass^k is the expensive path (k judge calls/run); run it on a sample
  or nightly, not every run, in production.
