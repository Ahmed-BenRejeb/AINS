# Sentinel — How It Works (plain-English component guide + worked example)

> For a reader who knows nothing about the project. Explains each moving part, why
> it exists, and then walks one real incident through the whole system end to end.

---

## 1. The problem in one paragraph

Companies are putting **AI agents** into production — software that reads a messy
ticket, reasons, calls tools, and takes actions (comment on a Jira issue, link a
duplicate, write a Confluence page). Unlike normal software, these agents are
**non-deterministic**: the same input can produce different steps and outputs each
run. So an agent can "look busy," call the right-looking tools, and still get the
answer wrong — and you only find out *after* it has touched a real ticket. Normal
tests (exact output matching) and normal logs (a flat text file you can't re-run)
don't work for this. Sentinel is the missing reliability layer.

---

## 2. The components (what each one is, in plain English)

### Flight Recorder (UC2) — the "black box" for an AI agent
Like an aircraft flight recorder. While the agent runs live, it **transparently
intercepts and tapes every step**: each LLM call (the prompt sent + the response),
each tool call (which tool, what arguments, what it returned). It stores them as a
**cassette** (the recorded tape) plus a **hash-chained, signed audit trail** (each
step is cryptographically linked to the previous one, so you can prove the record
wasn't tampered with).

Why it matters: you can later **replay** the exact run for debugging **without
hitting live APIs** — so debugging never re-sends a customer email or re-modifies a
ticket. It also gives compliance a tamper-evident record of "what did the agent see
and do."

- *Record:* every LLM/tool call → cassette (MinIO) + audit row (Cloudflare D1).
- *Replay:* re-run from tape → **0 live calls**; if the agent asks for something not
  on tape, that's flagged as a divergence instead of escaping to the network.
- *Bisect:* compare a good run vs a bad run and find the **first step where they
  diverge** — regression triage for agent behaviour.

### Eval Engine (UC1) — the "continuous evaluator / judge"
Takes a recorded run and decides, automatically, **did this agent actually do its
job?** It evaluates at multiple independent levels so the signals don't all come
from one place:
1. **Safety pre-filter** (Llama Guard) — is the content unsafe? short-circuit if so.
2. **Code grader** (deterministic) — schema valid? tool calls well-formed? no
   reasoning loops? token budget respected?
3. **LLM judge** (calibrated) — an LLM scores the run on rubric dimensions
   (correctness, efficiency, safety, reasoning quality). It runs **twice with the
   rubric reversed**; if the verdict flips, the judge is order-sensitive on this
   case → the verdict is downgraded to **uncertain** and flagged for a human.

It then produces an **EvalVerdict**: pass / fail / uncertain, per-dimension scores,
a **failure attribution** (which step + component caused a failure), a self-critique
+ confidence, and a recommended action — all human-readable.

Extra reliability signals:
- **pass^k** — run the same task k times; it only "passes" if **all k** pass. This
  exposes the non-determinism that a single run hides (our headline: pass@1 100% but
  pass^8 33%).
- **Drift detection** — compare two windows of runs over time; detect when pass rate,
  dimension scores, or output *style* (semantic embedding centroid) shift.
- **Evaluation of the evaluator** — score the judge itself against human labels with
  **Cohen's κ** (chance-corrected agreement), so you know how much to trust the judge.

### Atlassian Agent + Remote (UC3) — the real workload being watched
The thing the recorder + evaluator are pointed at: a real Atlassian incident-triage
agent. Given an incident, it embeds the text, does **semantic vector search** over
past incidents and runbooks, and an LLM **drafts a root-cause analysis** (hypothesis
+ cited evidence + severity + suggested team) that posts back to Jira as a comment.
It also resolves **semantic duplicates** (same bug, different words) and links them.
If confidence is low it **flags for a human** instead of acting — graceful degradation.

### Supporting infrastructure (the nouns you'll see)
- **Langfuse** — an open-source **LLM observability** UI (self-hosted). Every LLM
  call and vector search the system makes is sent to Langfuse as a *trace*, so you
  can browse, in a timeline, exactly what prompt went to which model, what came back,
  latency, etc. Think "Datadog/APM, but for LLM calls." It's the engineer-facing deep
  view; the dashboard is the product-facing view.
- **xqdrant** — the **vector database** (a Qdrant fork). Stores 768-dim embeddings of
  past incidents + runbooks so we can find *semantically* similar ones (not keyword).
- **Cloudflare Workers AI** — where the actual models run (embeddings = BGE-768,
  reasoning/judge = Llama 3.1 8B, safety = Llama Guard). No Anthropic/OpenAI key.
- **Cloudflare D1** — a SQLite database holding the trace metadata, run manifests, and
  eval verdicts (the structured records the dashboard reads).
- **MinIO** — S3-compatible blob storage for the full cassettes (the heavy tapes).
- **Dashboard** — the Next.js web app that ties it together: overview (pass rate,
  pass^k), runs, per-run trace, verdicts, and replay/bisect.

---

## 3. How the pieces connect (one loop)

```
incident ─▶ Atlassian Agent (UC3) ─▶ embed + vector search (xqdrant) ─▶ LLM drafts RCA
                  │                         every model/tool call ▲
                  │                                               │ taped live
                  ▼                                               │
            Flight Recorder (UC2) ── cassette (MinIO) + audit (D1) + Langfuse traces
                  │ run_id
                  ▼
            Eval Engine (UC1) ─▶ safety + code grader + calibrated judge
                  │            ─▶ EvalVerdict (D1): verdict, dims, attribution, pass^k
                  ▼
            Dashboard ─▶ overview / trace / verdict / replay   (+ Jira incident on fail)
```

Remove the AI and nothing here exists: there is no rule that tells you an agent that
"looked busy" actually failed, and no keyword query that finds a duplicate phrased
differently.

---

## 4. Worked example — incident AO-11, step by step

**Input (a real Jira incident, AO-11):** *"Connection pool exhaustion cascading to
all services — cascading failures traced to connection pool depletion."*

**Step 0 — Trigger.** `POST /analyze {incident_key: "AO-11"}`. The backend assigns a
`run_id` and opens a Flight-Recorder recording scope.

**Step 1 — Embed (recorded).** The incident text is embedded once via BGE-768.
→ trace step: `embedding` on `bge-base-en-v1.5`, output "1 vector, 768-dim". Taped
to the cassette + audit chain; sent to Langfuse.

**Step 2 — Search similar incidents (recorded tool call).** The vector queries the
`incidents` collection in xqdrant. → trace step: `vector search` incidents,
top hit `0.99` ("Connection pool exhaustion cascading to all services"). Attribution
(confidence margin to the next hit) is attached.

**Step 3 — Search runbooks (recorded tool call).** Same vector queries the `runbooks`
collection. → `vector search` runbooks, e.g. "Database Connection Pool Exhaustion"
at `0.72` (above the 0.60 runbook floor).

**Step 4 — Draft RCA (recorded LLM call).** Llama 3.1 8B is given the incident +
retrieved evidence and returns a **structured** `RcaDraft`: root-cause hypothesis,
evidence list (citing the hits above), `proposed_severity: critical`, suggested team,
confidence. → trace step: `llm chat`. This posts to Jira as an ADF comment.

**Step 5 — Record finalised.** The cassette now holds 4 steps + a hash-chained audit
trail; a `run_manifests` row is written; the run is replayable.

**Step 6 — Evaluate (UC1).** The eval engine loads the run and judges it:
- safety: pass; code grader: schema + tool calls valid;
- LLM judge ×2 (rubric reversed): dimension scores (correctness 0.9, etc.);
- here the two passes **disagreed** → verdict **uncertain**, `flag_for_human: true`
  (this is the calibration catching judge instability — a feature, not a bug).
- An `EvalVerdict` is persisted to D1 and (because it's flagged) an AO Jira Incident
  is filed.

**Step 7 — Inspect (dashboard).**
- `runs/<run_id>` → the 4-step timeline above, each step readable.
- `verdicts/<run_id>` → verdict, per-dimension scores, self-critique, recommended action.
- `replay/<run_id>` → the recorded trajectory + **Launch replay** → `live_call_count: 0,
  diverged: false` (proves reproducibility), plus bisect vs another run.
- Langfuse → the same calls as raw LLM traces for an engineer.

**Step 8 — Reliability over many runs.** Re-run AO-11 several times and the verdict
isn't always the same (non-determinism). `pass^k` quantifies it: across the demo set,
pass@1 is high but **pass^k is far lower** — the single number that tells a platform
owner "this agent is not yet reliable enough to run unattended."

---

## 5. Where to look during a demo

| Question a viewer asks | Where to point | What they see |
|---|---|---|
| "What did the agent actually do?" | dashboard `runs/<id>` | 4-step recorded trajectory, readable |
| "Did it do it *right*?" | dashboard `verdicts/<id>` | verdict + per-dimension + attribution |
| "Can you prove/replay it?" | dashboard `replay/<id>` | recorded steps + 0 live calls on replay |
| "Show me the raw LLM calls" | Langfuse | per-call prompt/response/latency traces |
| "How reliable is it overall?" | dashboard home | pass rate + true pass^k + flagged count |
| "What landed in Atlassian?" | Jira project AO | RCA comment + auto-filed verdict incidents |
