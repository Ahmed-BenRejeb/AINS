# Sentinel — Response to the Official Technical Specification

> Point-by-point response to **every** requirement in `docs/TECHNICAL_SPECS.md`
> (AINS 2026 brief): what we did, where it lives, where the gaps are (honestly), and
> why the approach is innovative. Companion to `docs/validation_guide.md` (how to
> test each item) and `docs/how_it_works.md` (plain-English component guide).

Legend: ✅ done & live · 🟦 built, Forge-cloud deploy pending · ⬜ not done.

---

## 1. Global Requirements

### 1.3 What a good solution must achieve
| # | Requirement | Our response |
|---|---|---|
| 1 | **AI is the mechanism, not a feature** | ✅ Remove the AI and nothing remains: there is no rule that detects an agent "looked busy but failed", no keyword query that finds a duplicate phrased differently, and no deterministic test for a non-deterministic agent. Every core output (verdict, RCA, duplicate link, drift, attribution) is produced by an LLM-judge / embedding-retrieval / calibrated-evaluation mechanism. |
| 2 | **Actionable outputs** | ✅ Structured `EvalVerdict` (verdict + per-dimension scores + failure attribution + recommended action), `RcaDraft` (hypothesis + evidence + severity), hash-chained audit records, `DriftReport`, `pass^k` — never open-ended chat. |
| 3 | **Structural intelligence beyond retrieval** | ✅ Classification (verdict), detection (drift, safety), attribution (which step failed), generation (RCA), chance-corrected meta-evaluation (Cohen's κ). Retrieval is one input, not the product. |
| 4 | **Explainability** | ✅ Every verdict traces to a recorded trajectory + per-dimension reasons + a self-critique + a confidence flag; every RCA cites the specific incidents/runbooks it used; Langfuse holds the raw LLM traces. |
| 5 | **Evaluation** | ✅ A real protocol: `pass^k` over a synthetic test set (`docs/eval_report.md`: pass@1 100% / pass^8 33%), plus per-dimension scores and the evaluator's own κ. Non-determinism is handled head-on (it is the thesis). |

### 1.4 What is not allowed (we avoid all four)
- **Not a chatbot** — there is no conversational assistant; the system runs an evaluation/recording pipeline.
- **Not a thin wrapper around an Atlassian feature** — Jira has no agent-reliability layer, no semantic dedup, no deterministic replay.
- **Not a clone** — the combination (flight-recorder + continuous evaluator + the agent it watches, with a replay-cassette + audit-trail protocol contribution) is original.
- **No manual setup during the demo** — `/analyze` runs trigger-to-output autonomously; `?mock=true` is only a presentation safety net, clearly badged.

### 1.6 Non-functional expectations
- **Responsiveness** ✅ — `/analyze` end-to-end ~20–45s on the free 8B model (embed + 2 searches + RCA + calibrated judge), inside Forge's 25s for the user-facing call (eval is async/after).
- **Reliability** ✅ — missing/odd data never crashes: upstream LLM outages map to a clean **503**; low confidence → `flag_for_human`; Jira/D1/recorder writes are best-effort; the dashboard degrades to an honest empty state.
- **Scalability mindset** ✅ — documented in `docs/validation_guide.md` §6 (xqdrant ANN, per-run bounded cost, stateless services, run pass^k on a sample/nightly).

---

## 2. UC1 — Continuous Evaluation (acceptance criteria §2.4)

| Criterion | Priority | Status | Where |
|---|---|---|---|
| Trajectory capture | Must | ✅ | recorded trace, 4 steps, inspectable on `dashboard/runs/{id}` |
| Multi-level evaluation | Must | ✅ | **3 independent levels**: safety filter + deterministic code grader + calibrated LLM judge → distinct signals |
| Failure attribution | Must | ✅ | `FailureAttribution` (step + component), VeriLA-style DAG attributor |
| Human-readable verdict | Must | ✅ | `EvalVerdict` with recommended action, on `dashboard/verdicts/{id}` |
| Drift detection | Should | ✅ | `POST /drift` (pass-rate + per-dimension + semantic BGE-centroid drift) |
| Non-determinism addressed | Should | ✅ | `pass^k` (all-k), calibrated judge → `uncertain`, documented |
| Evaluation of the evaluator | Should | ✅ | `POST /evaluator-quality` → Cohen's κ vs human gold labels |

**All UC1 Musts and Shoulds are met.**

---

## 3. UC2 — Flight Recorder / Replay (acceptance criteria §3.4)

| Criterion | Priority | Status | Where |
|---|---|---|---|
| Record functionality | Must | ✅ | every LLM + tool call taped → cassette (MinIO) + hash-chained audit (D1) |
| Deterministic replay | Must | ✅ | `POST /replay` → 0 live calls, no divergence |
| State inspection | Must | ✅ | exact per-step input/output on `dashboard/runs/{id}` + `dashboard/replay/{id}` |
| Divergence editing | Should | 🟦→✅ (bisect) | `POST /bisect` finds the first diverging step (same-incident good/bad pair via `make bisect-demo`). Full *mid-replay prompt injection* (edit a value and continue) is the one **partial** item — see Gaps. |

**Both Musts met; the Should is met as bisect-based divergence detection; live prompt-injection-during-replay is the remaining stretch.**

---

## 4. UC3 — Atlassian Workflow (acceptance criteria §4.4)

| Criterion | Priority | Status | Where |
|---|---|---|---|
| End-to-end workflow | Must | ✅ | `/analyze`: incident → retrieve → RCA → Jira comment; `/duplicates`: semantic dedup + auto-link |
| AI necessity verified | Must | ✅ | argued in `validation_guide.md` §4 (semantic retrieval + synthesis + judgement, impossible with IF/THEN) |
| Actionable output | Must | ✅ | `RcaDraft` → ADF Jira comment; duplicate link + comment; verdict → AO Incident |
| Evaluation metric | Should | ✅ | the RCA agent is itself measured by UC1 (pass^k + dimensions) |
| Graceful degradation | (key) | ✅ | `flag_for_human` below confidence thresholds; never auto-acts when unsure |

**All UC3 criteria met at the backend + agent level. The Rovo agent is registered (real app ARI) and the compute + Jira/Confluence read-write are live; the final `forge deploy`/`install` to the Atlassian cloud is the deployment step that remains (🟦).**

---

## 5. Judging Criteria (§5.1) & Bonus (§5.2)

| Dimension (weight) | How we score |
|---|---|
| **Engineering depth (50%)** | Three real infrastructure systems: a transparent httpx-transport recorder with a tamper-evident hash chain, a calibrated LLM-judge with position-bias detection + pass^k, and a VeriLA-style attributor — plus a shared OTel-GenAI schema. The AI *is* the system. |
| **Prototype quality (25%)** | End-to-end live on a real Atlassian site; 5+ demo incidents; structured inspectable outputs; dashboard with 5 screens; degrades gracefully; `?mock=true` safety net. |
| **Explainability (15%)** | Per-step trace, per-dimension verdict reasons, cited RCA evidence, confidence flags, Langfuse raw traces, replay + bisect. |
| **Evaluation & rigour (10%)** | Real `pass^k` run (100%→33%), per-dimension scores, drift, **and the evaluator's own κ** — non-determinism is the central thesis, not an afterthought. |

**Bonus:**
- ✅ **Protocol gap documented** — `spec/otel-genai-replay-extension.md` (replay cassette OTel attributes) + `spec/mcp-audit-trail-proposal.md` (hash-chained MCP audit trail).
- ✅ **Self-evaluation** — `SelfEvaluation` (confidence + self-critique) + position-bias calibration surfacing low-confidence verdicts.
- 🟦 **Real enterprise validation** — `docs/validation_guide.md` is the harness + remarks template; needs one external engineer to run it and sign off.
- ✅ **Open contribution** — the two `spec/*.md` artefacts + the reusable `trace-core` schema.

---

## 6. What is innovative here

1. **One loop that is all three use cases.** Most teams pick one UC. Sentinel's agent (UC3) is *instrumented by* the recorder (UC2) and *judged by* the evaluator (UC1) — the use cases compose into a single reliability platform, which is exactly how this would ship in a real Marketplace vendor.
2. **pass^k as the headline, not pass@1.** We surface the τ-bench insight (100% pass@1 collapsing to 33% pass^8) directly in the product — the single number that tells a platform owner an agent isn't safe to run unattended. Few demos quantify non-determinism this honestly.
3. **Calibrated judge + evaluation-of-the-evaluator.** We don't just LLM-judge; we run each judgement twice with the rubric reversed (position-bias detection → `uncertain`) and we score the judge itself against human labels with chance-corrected Cohen's κ. We evaluate the evaluator.
4. **Tamper-evident replay protocol.** The cassette + hash-chained, HMAC-signed audit trail is a concrete, documented protocol contribution (the two `spec/*.md`), not just a feature — replay is provably the same run (0 live calls), and the audit chain is verifiable.
5. **Explainable retrieval.** xqdrant hits always carry an attribution (confidence margin to the next hit), so a human sees *why* a similar incident/runbook was chosen.
6. **Honest engineering under constraints.** Per-collection similarity floors, a cheap-model judge with the quality trade-off made visible *in the metrics*, graceful 503s, and a dashboard that shows an honest empty state rather than fake numbers.

---

## 7. Honest gaps (and the path to close them)

| Gap | Impact | Path |
|---|---|---|
| **Forge cloud deploy** of the Rovo agent (`forge deploy`/`install`) | The agent's native in-Atlassian UI isn't live (the backend + read/write are) | Run `forge deploy --environment development` + `forge install` from a workstation with an Atlassian login |
| **Mid-replay prompt injection** (UC2 "Should": edit a value during replay and continue) | We do bisect-based divergence, not live injection-and-continue | Add an inject hook to the replay engine that overrides a step's recorded response and lets the agent continue |
| **Larger judge model** | The free 8B judge is noisier (more `uncertain`), visible in pass^k | Point `CF_AI_MODEL_MAIN` at a stronger model for the demo; keep 8B for cost |
| **Richer runbook content** | Templated seed runbooks cap incident→runbook cosine ~0.71 (handled with a 0.60 floor) | Re-seed real remediation content |
| **External enterprise sign-off** (bonus) | Not yet collected | Hand `validation_guide.md` to one platform owner to run + fill the remarks table |
| **Public-API auth** (security) | Addressed in the security pass — see `docs/security_audit.md` | — |

**Bottom line:** every **Must** across UC1/UC2/UC3 is met and live; every **Should** is met except live mid-replay injection (we provide bisect instead); the main remaining deployment step is the Forge cloud install.
