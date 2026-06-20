# Sentinel — Full Technical Battle Plan
## AINS Hackathon 2026 · Vectors (covectors.io)

> This is the authoritative technical strategy document. Read it before making any architecture, stack, or scope decision.
> For the official judging criteria and use case specs, see `docs/TECHNICAL_SPECS.md`.

> **⚠️ Stack reality update (post-setup).** This plan predates the final infrastructure decisions.
> The deployed stack substitutes: **Cloudflare Workers AI** for all LLM/embedding/safety calls
> (no Anthropic / Claude / `claude-sonnet`), **MinIO** for blob storage (not Cloudflare R2),
> **xqdrant** for similarity search (not Vectorize), and **skips Cloudflare Queues** (evaluation
> runs synchronously). Wherever this document says Anthropic/Claude, R2, Vectorize, or Queues,
> apply those substitutions. The deployed state in root `CLAUDE.md` §0 + §9 is authoritative.

---

## 1. The Core Strategy: One System, Not Three Projects

All three use cases share a single OTel GenAI trace spine:

```
[UC3 Atlassian Agent]   ← the real agent we instrument
        ↓  emits gen_ai.* spans
[UC2 Flight Recorder]   ← captures + stores + replays traces
        ↓  feeds traces to
[UC1 Eval Engine]       ← judges traces, produces verdicts
        ↓  files verdicts as
[Jira Issues / Confluence Reports]  ← back into Atlassian
```

**The winning narrative:** *"We built the reliability infrastructure a Marketplace AI vendor needs, and dogfooded it on a real Atlassian agent."*

This is not three disconnected demos. It is one coherent system where each layer is independently valuable but becomes dramatically more powerful in combination.

---

## 2. Who is Vectors — and What Impresses Them

**Vectors (covectors.io)** is an Atlassian Marketplace vendor (~21–50 people, 2022 spin-off of French consultancy Spectrum Groupe) that builds knowledge-management apps for Confluence and Jira: Glossary, FAQ, Ideation, Content Formatting, Discussions. They recently acquired Caelor (another Marketplace partner) and launched AI-powered Confluence formatting features.

**What impresses them specifically:**
1. Clean, idiomatic **Atlassian-native engineering** (Forge, correct data models)
2. Anything touching **knowledge structuring and retrieval** — their entire product thesis
3. **Production-grade reliability tooling for AI** — because as a Marketplace vendor shipping AI features, they face UC1/UC2 problems themselves

**UC3 tactical implication:** build something that *structures and surfaces knowledge* (incident RCAs → runbooks → PIRs → knowledge-gap detection). This mirrors their domain exactly and signals "you understand their world."

---

## 3. Atlassian Crash Course (Zero to Ready)

### The Three Products

| Product | What It Is | Analogy |
|---|---|---|
| **Jira** | Issue/work tracking. Projects, issues, sprints, JQL queries, workflows | GitHub Issues + Linear |
| **Confluence** | Wiki and knowledge base. Spaces → Pages, rich content | Notion (enterprise) |
| **JSM** | ITSM on top of Jira. Customer portal, incidents, SLAs | Zendesk + PagerDuty |

### Free Dev Site Setup (Do This First)
1. Go to **https://go.atlassian.com/cloud-dev** → free cloud dev site
2. Create an API token: **https://id.atlassian.com/manage-profile/security/api-tokens**
3. Install Forge CLI: `npm install -g @forge/cli && forge login`
4. Verify: `curl -u "email:TOKEN" "https://your-site.atlassian.net/rest/api/3/myself"`

### Key API Patterns

```bash
# Jira: https://your-site.atlassian.net/rest/api/3/
# Confluence: https://your-site.atlassian.net/wiki/rest/api/
# JSM: https://your-site.atlassian.net/rest/servicedeskapi/   ← different pagination!

# Jira uses startAt/maxResults pagination
# JSM uses start/limit pagination
# Mixing them silently truncates results — a common gotcha
```

**Auth:** `Authorization: Basic base64(email:api_token)`

**Rate limits (enforced March 2, 2026):** Points-based, 65k points/hr global pool. Returns HTTP 429 with `Retry-After`. Always implement exponential backoff. No exceptions.

**Content format:** Jira and Confluence use **Atlassian Document Format (ADF)** for rich text — not plain strings or Markdown. Every comment/page body must be valid ADF JSON.

### Forge vs Connect vs Plain REST

| | Use When | Status |
|---|---|---|
| **Forge** | Building a native Atlassian app or Rovo Agent | ✅ Active — use this for UC3 |
| **Connect** | — | ❌ Being sunset — never start new projects on this |
| **Plain REST** | External scripts, data seeding, our Python backends | ✅ Use for everything outside Atlassian |

### MCP Quick Access
Atlassian's official Remote MCP Server (GA Feb 2026):
- Endpoint: `https://mcp.atlassian.com/v1/mcp` (OAuth 2.1, ~16 tools)
- Use for fast prototyping and Claude Code integration

---

## 4. UC2 — Flight Recorder & Deterministic Replay

### What We Build

A transparent capture-and-replay layer for any AI agent. The agent runs normally; the flight recorder intercepts every LLM API call and tool call without the agent knowing, stores the full input/output/metadata, and enables deterministic replay where the agent re-runs identically using stored responses instead of live APIs.

### The Core Technical Approach

**Two interception layers:**

```python
# Layer 1: LLM HTTP Proxy (httpx transport override)
# Wraps the Anthropic/OpenAI client — no agent code change required
class RecordingTransport(httpx.BaseTransport):
    def handle_request(self, request):
        step_key = hash_request(request)  # normalize + hash (strips timestamps/UUIDs)
        if self.mode == "replay" and step_key in self.cassette:
            return stored_response(self.cassette[step_key])
        response = self._forward(request)
        if self.mode == "record":
            self.cassette[step_key] = response.json()
            write_audit_record(step_key, request, response)
        return response

# Layer 2: Tool/MCP Decorator
@record_tool(run_id=current_run_id, mode=FLIGHT_MODE)
def create_jira_issue(summary: str, description: str) -> dict:
    ...  # real implementation unchanged
```

**Critical design decision — Structured JSON plans (AgentRR insight):**
Tool dispatch must use Pydantic structured output — never free-text parsing. If the LLM says "I'll call create_jira_issue" in prose and you parse it out, replay is non-deterministic. If the LLM outputs `{"tool": "create_jira_issue", "args": {...}}` as a structured type, replay is deterministic.

**Bisect engine:** Given two run IDs (one good, one bad), find the first step where outputs diverge. The engineer can then inject a corrected value at that exact step and replay the remainder to verify the fix.

**Hash-chained audit trail:**
```json
{
  "run_id": "uuid",
  "step_id": "uuid",
  "kind": "llm_call",
  "input": {"...": "..."},
  "output": {"...": "..."},
  "audit": {
    "prev_hash": "sha256:...",
    "payload_hash": "sha256:...",
    "hmac": "sha256:..."
  }
}
```
Records are written **before** execution (write-ahead logging). The chain is tamper-evident — any modification breaks it.

### What Exists vs What We Add

| Library | What It Does | Our Gap-Fill |
|---|---|---|
| llm-rewind (PyPI) | Python LLM HTTP proxy, record/replay/bisect | No MCP, no eval integration, no audit trail |
| vcrpy | HTTP cassettes for Python | Not agent-aware, no state snapshots |
| langchain-replay | LangChain decision replay | LangChain-only, no injection/fork |
| LangGraph Time Travel | Checkpoint-based step-back | Requires LangGraph architecture |

**Our differentiator:** MCP-aware dual-layer proxy + hash-chained audit + bisect + fork/inject + direct UC1 integration.

### Storage
- **D1 (SQLite):** trace metadata, step index, run manifests — structured queries
- **R2 (Object storage):** full prompt/response blobs, cassettes — no size limit, no egress fees
- Schema: `infra/cloudflare/d1-schema.sql`

---

## 5. UC1 — Continuous Evaluation System

### What We Build

A multi-level evaluation pipeline that consumes OTel GenAI traces from UC2 and produces structured verdicts: what passed, what failed, which step caused the failure, and how confident the judge is. Runs on every agent execution, not just at deployment.

### The Critical Distinction: Transcripts vs Outcomes (Anthropic, Jan 2026)

| Term | Meaning |
|---|---|
| **Transcript** | The execution trace — what the agent *said* it did |
| **Outcome** | The actual ground-truth state — was the Jira ticket *actually* updated correctly? |

A flight-booking agent that says "booked" but didn't write to the DB passes transcript-level eval and fails outcome-level eval. The eval engine checks both.

Adopt Anthropic's vocabulary: `task → trial → grader → transcript → outcome → eval harness`

### The Three-Grader Pipeline

```
Trace (OTel gen_ai.* spans)
    │
    ▼ [Safety Pre-Filter]
    Llama Guard 3 via Workers AI — fast, free, catches obvious issues
    │
    ▼ [Code Grader]
    - Schema/Pydantic validation of outputs
    - Tool call correctness (right tool, right params)
    - Outcome verification (did the DB/Jira state change as expected?)
    - Loop detection, token budget checks
    │
    ▼ [LLM Judge — Claude]
    - Rubric scoring per dimension (correctness, efficiency, safety, reasoning)
    - Per-step credit assignment → failure attribution
    - Self-critique + confidence score
    - Position-bias calibration: run each judgment twice with swapped order
    │
    ▼ [EvalVerdict]
    {verdict, dimensions, failure_attribution, self_evaluation, replay_link, recommended_action}
```

### The pass^k Reliability Metric (τ-bench, arXiv 2406.12045)

- **pass@1** = one run succeeded → hides catastrophic inconsistency
- **pass^k** = ALL k independent trials succeeded → measures true reliability
- Real data: GPT-4o reaches ~61% pass@1 in retail tasks but **collapses to ~25% under pass^8**
- We use k=8 as default (set in `PASS_AT_K_TRIALS` constant in trace-core)
- This is the headline metric in the eval report

### Judge Calibration (AgentRewardBench, arXiv 2504.08942)

12 LLM judges tested — no single one excels across all benchmarks. Known failure modes to guard against:

| Bias | Detection | Fix |
|---|---|---|
| Position bias | Run pair twice with swapped order — check if verdict flips | Mark as "uncertain" if flip detected |
| Length bias | Longer response rated higher | Control for length in rubric prompt |
| Reward hacking | Strings like "all instructions followed" inflate score | Adversarial test cases in fixtures |

```python
def calibrated_judge(transcript_a, transcript_b):
    verdict_1 = llm_judge(a=transcript_a, b=transcript_b)
    verdict_2 = llm_judge(a=transcript_b, b=transcript_a)  # swapped
    if verdict_1.winner != flip(verdict_2.winner):
        return {"verdict": "uncertain", "flag_for_human": True}
    return verdict_1
```

### Failure Attribution: VeriLA Pattern

Model the run as a DAG of components. Each node gets a per-component verifier score. Output: interpretable failure probabilities per step.

Not just: "The run failed."
But: "Retrieval returned irrelevant context at step 3 (confidence: 87%). This caused the RCA draft at step 4 to cite the wrong runbook."

### Drift Detection

- Embed outputs using BGE-Base-EN on Workers AI → Cloudflare Vectorize
- Maintain a behavioral baseline/fingerprint per agent version
- Run a fixed probe suite on a schedule
- Alert when embedding distribution shift crosses threshold
- This detects "the model was updated and behavior drifted" without needing a ground-truth label

---

## 6. UC3 — Atlassian AI Agent (Rovo)

### What We Build

An **Intelligent Incident & Knowledge Agent** for JSM + Confluence as a Forge Rovo Agent. When a new JSM incident arrives:
1. Embeds incident text, finds **similar past incidents** + **relevant Confluence runbooks** via vector search
2. Drafts a **root cause hypothesis** citing specific evidence
3. Detects **semantic duplicates** (different phrasing, same issue)
4. Proposes **severity + assignee** based on similar past patterns
5. On resolution: drafts a **Post-Incident Review (PIR)** Confluence page
6. Flags **knowledge gaps** — incidents with no matching runbook → creates Confluence stubs

### Why This is Provably Beyond IF/THEN Automation

Jira Automation rule: `IF issue_type == "Incident" AND priority == "High" THEN assign_to("ops-team")`

Our agent: reads unstructured incident text, retrieves semantically similar incidents despite different phrasing ("DB timeout" ↔ "database connection refused" ↔ "pool exhausted"), reasons about root cause, detects duplicates without keyword overlap, generates structured PIR from an unstructured incident thread.

**Remove the LLM → system stops working entirely.** This is the judge test.

### Multi-Agent Pattern (Planner → Generator → Evaluator)

```python
async def incident_rca_workflow(incident_id: str) -> RCAResult:
    # 1. Retriever (Forge Remote → atlassian-remote)
    incident = await fetch_incident(incident_id)
    similar   = await vector_search(incident.text, index="incidents", k=5)
    runbooks  = await vector_search(incident.text, index="runbooks", k=3)

    # 2. RCA Generator (Claude, structured Pydantic output)
    draft_rca = await generate_rca(incident, similar, runbooks)

    # 3. Evaluator (UC1 system — this closes the loop)
    verdict = await eval_engine.evaluate(draft_rca, ground_truth=incident)

    if verdict.confidence < CONFIDENCE_THRESHOLD:
        return RCAResult(status="needs_human_review", draft=draft_rca)

    # 4. Post to Atlassian
    await post_jira_comment(incident_id, draft_rca)
    await create_confluence_pir(incident, draft_rca)
    return RCAResult(status="posted", verdict=verdict)
```

### Forge Rovo Agent Structure

```yaml
# manifest.yml
modules:
  rovo:agent:
    - key: incident-rca-agent
      name: Incident RCA Agent
      prompt: |
        You are an incident analysis expert. For each new incident:
        1. Fetch the incident details (fetch-incident)
        2. Find similar past incidents (search-similar-incidents)
        3. Find relevant runbook pages (search-runbooks)
        4. Draft a structured RCA: root_cause, evidence, severity_rationale,
           proposed_assignee, duplicate_check, knowledge_gaps, confidence_score
        5. If confidence < 70%, flag for human review. Never post if no
           relevant similar incidents or runbooks found.
      actions:
        - fetch-incident
        - search-similar-incidents
        - search-runbooks
        - post-rca-comment
        - draft-pir-page
        - flag-knowledge-gap
```

### Forge Remote Pattern

Heavy compute runs on Azure VM, not in Forge's sandbox (25s timeout limit):
```
Forge Action → callRemote() → Azure VM FastAPI (port 8080)
                               ↓
                    embed text → Workers AI
                    vector search → Vectorize
                    LLM reasoning → Anthropic API
                    return RcaDraft (Pydantic)
```

Every Forge Remote call must include `X-Sentinel-Secret` + `X-Account-Id` headers.

---

## 7. Tech Stack Master Reference

### Models

| Use | Model | Provider | Reason |
|---|---|---|---|
| RCA generation, eval judging | `claude-sonnet-4-6` | Anthropic API | Best reasoning-to-cost ratio |
| Safety pre-filter | `llama-guard-3-8b` | CF Workers AI | Free tier, instant, 10k neurons/day |
| Embeddings | `bge-base-en-v1.5` | CF Workers AI | Free tier, 768-dim, cosine sim |
| Cheap rubric scoring | `llama-3.3-70b-instruct-fp8-fast` | CF Workers AI | Fast, cheap, structured output |

### Frameworks

| Layer | Choice | Why |
|---|---|---|
| Agent framework | LangGraph | State persistence, checkpoints, Time Travel replay |
| LLM instrumentation | OpenLLMetry (`traceloop-sdk`) | OTel-native, auto-instruments LangGraph |
| Observability UI | Langfuse (self-hosted, MIT) | OTel-native, best OSS eval store |
| Forge app | Forge TypeScript SDK | Mandatory for Atlassian-native Rovo agents |
| HTTP interception | httpx transport override | No proxy process, works inside SDK |
| Eval framework | DeepEval | Built-in metrics (G-Eval, RAGAS, hallucination) |
| Vector search | Cloudflare Vectorize | Already in infra, no extra setup |
| Trace metadata | Cloudflare D1 (SQLite) | Serverless, no DB to manage |
| Blob storage | Cloudflare R2 | No egress fees, S3-compatible |
| Dashboard | Next.js 14 + shadcn/ui | Fast to build, great trace visualization |

### Language Split

| Area | Language |
|---|---|
| Forge app (UC3) | TypeScript (mandatory for Forge) |
| Eval engine (UC1) | Python |
| Flight recorder (UC2) | Python |
| Atlassian remote backend | Python |
| Dashboard | TypeScript (Next.js) |
| Scripts | Python |

---

## 8. Infrastructure

### Topology

```
Azure VM (one shared dev environment)
  ├── Langfuse + Postgres (Docker, port 3000)
  ├── eval-engine FastAPI (systemd, port 8000)
  ├── atlassian-remote FastAPI (systemd, port 8080)
  └── cloudflared daemon → Cloudflare Tunnel → yourdomain.com

Cloudflare
  ├── D1: trace metadata + verdicts
  ├── R2: cassettes + blobs
  ├── Vectorize: incident + runbook embeddings
  ├── Workers AI: Llama Guard 3, BGE embeddings
  ├── Queues: async eval jobs
  └── Tunnel: stable HTTPS endpoint for Azure VM

Atlassian (free dev site)
  ├── JSM: incidents (seeded via make seed)
  ├── Confluence: runbooks (seeded via make seed)
  └── Forge: atlassian-agent deployed via forge deploy
```

### Azure for Students
- **$100 credit / 12 months**, no credit card required
- Recommended VM: **Standard_B2s** (2 vCPU, 4 GB RAM)
- OS: Ubuntu 22.04 LTS
- Only open port: **22 (SSH)** — all other traffic via Cloudflare Tunnel
- Setup: `bash infra/azure/setup.sh`

### Cloudflare Tunnel vs ngrok

| | Cloudflare Tunnel | ngrok |
|---|---|---|
| Cost | **Free** | Limited free tier |
| URL stability | **Stable (your domain)** | Rotates on free tier |
| Session timeout | **None** | 8 hours |
| Best for | Persistent webhook endpoint (Jira → your service) | Ad-hoc payload inspection |

**Rule:** Cloudflare Tunnel for the shared Azure VM endpoint. ngrok for individual debugging.

**Team collaboration:** everyone connects to the single shared Azure VM:
```bash
ssh -L 3000:localhost:3000 user@azure-vm   # Langfuse
ssh -L 8000:localhost:8000 user@azure-vm   # Eval API
# Or just hit the Cloudflare Tunnel URL from anywhere
```

---

## 9. Implementation Phases

### Phase 0 — Foundation (Hours 0–4)
Stand up the shared infrastructure. Nothing else starts until this is done.

| Task | Gate |
|---|---|
| Azure VM provisioned, Langfuse running | Langfuse UI loads at `https://langfuse.yourdomain.com` |
| Cloudflare D1 + R2 + Vectorize + Tunnel configured | `wrangler d1 list` shows sentinel-traces |
| Atlassian free dev site created | `curl .../rest/api/3/myself` returns your account |
| `forge create` → hello-world Rovo agent deployed | Agent visible in Atlassian dev site |
| One agent run emits `gen_ai.*` spans into Langfuse | Spans visible in Langfuse UI |

**🛑 Do not start Phase 1 until spans are visible in Langfuse.**

### Phase 1 — UC2 Flight Recorder (Hours 4–14)

| Task | Notes |
|---|---|
| httpx transport override (LLM proxy) | Start simple: record mode only |
| Tool/MCP call decorator | Wrap 2–3 tools as proof of concept |
| Append-only JSONL → D1 + R2 | Hash-chained from the start |
| Basic replay mode | Return stored response, assert zero live calls |
| Bisect engine | Diff two run IDs, find first diverging step |

**🛑 Gate:** record a run, replay it, zero live API calls confirmed.

### Phase 2 — UC1 Eval Engine (Hours 4–14, parallel with UC2)

| Task | Notes |
|---|---|
| Code grader: schema validation + tool-call correctness | Easiest — start here |
| Outcome verification (Jira/Confluence state check) | The transcript vs outcome split |
| LLM judge (Claude, rubric scoring) | Use Anthropic SDK with structured output |
| Position-bias calibration | Run every judgment twice, swapped |
| pass^k metric (k=8 trials) | τ-bench standard |
| Verdict → D1 + auto-file Jira issue on failure | |

**🛑 Gate:** one run → one human-readable verdict with failure attribution + replay link.

### Phase 3 — UC3 Atlassian Agent (Hours 14–24)

| Task | Notes |
|---|---|
| `make seed` — 100 incidents + 20 runbooks | Run early so embeddings can be built |
| Embed all seed data → Vectorize | BGE-Base-EN on Workers AI |
| Forge Remote endpoint (FastAPI on Azure VM) | `/analyze`, `/search`, `/embed`, `/health` |
| Forge Rovo agent: 4 core actions | fetch-incident, search-similar, search-runbooks, draft-rca |
| Webhook trigger: new JSM incident → agent fires | |
| Post RCA comment to Jira + draft PIR to Confluence | |

**🛑 Gate:** synthetic incident → RCA comment in Jira + PIR page in Confluence, end-to-end.

### Phase 4 — Integration & Close the Loop (Hours 24–32)

| Task | Notes |
|---|---|
| Wire UC3 runs into UC1/UC2 | Every incident response is evaluated and recorded |
| Bisect integration in dashboard | Click a verdict → open replay → bisect button |
| Injection/fork mode in UC2 | Modify a step value → fork and replay remainder |
| Embedding drift detection | Compare output distributions across run batches |
| Unified dashboard | Trace → verdict → replay → incident — all linked |

### Phase 5 — Differentiators & Demo Polish (Hours 32–40)

| Task | Notes |
|---|---|
| Self-evaluation: judge critiques its own verdicts | Low-confidence → auto-file "needs human review" Jira issue |
| Knowledge gap flagging in UC3 | No matching runbook → create Confluence stub |
| `/spec` protocol gap documents | OTel replay extension + MCP audit trail |
| End-to-end demo rehearsal × 3 | The full story: incident → RCA → failure → replay → bisect → fix |
| Evaluation report | `make eval` → `docs/eval_report.md` |
| Pitch deck (15 slides max) | |

### Scope-Cut Order (If Behind)

Drop in this exact order. Never re-order.
1. ⬇️ Embedding drift dashboard (keep the data pipeline, drop the UI)
2. ⬇️ Injection/fork mode in UC2 (keep bisect — it's more impressive)
3. ⬇️ Multi-agent Planner/Generator/Evaluator (collapse to single orchestrator)
4. ⬇️ Knowledge gap flagging (keep duplicate detection)
5. ✅ **Never drop:** OTel trace spine, record/replay, code grader, one LLM judge, one end-to-end Atlassian workflow

---

## 10. Differentiation & Bonus Points

### Protocol Gap 1: OTel GenAI Has No Replay Standard

The OTel GenAI semantic conventions are **experimental** (opt-in via `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`). **Gap:** no standard for attaching a deterministic replay manifest to a trace, and no stable evaluation event schema.

**Our contribution** (`spec/otel-genai-replay-extension.md`): define `gen_ai.replay.*` and `gen_ai.eval.*` span attributes with a reference implementation in `packages/flight-recorder`.

This is a verifiable, real protocol gap. Judges can check it.

### Protocol Gap 2: MCP Has No Audit Trail Standard

MCP has no standardized way to record what tools an agent called across sessions with tamper-evident proof.

**Our contribution** (`spec/mcp-audit-trail-proposal.md`): hash-chained, HMAC-signed audit records written before execution, with a reference implementation in `packages/flight-recorder/audit/`.

### Self-Evaluation (Bonus Point)

Every verdict includes:
```json
{
  "self_evaluation": {
    "judge_confidence": 0.73,
    "self_critique": "Attribution based on incomplete retrieval evidence. Human review recommended.",
    "flag_for_human": true
  }
}
```

Low-confidence verdicts auto-create a `priority: "Human Review Required"` Jira issue. Demo this live.

### The Demo Story (Rehearse This Exactly)

> "We deployed an AI agent to triage and analyze Jira incidents. We ran it on 100 synthetic incidents. Our Flight Recorder captured every step. Our Eval Engine flagged that on 12 out of 100 runs, the agent proposed the wrong severity — and they all looked successful because no error was thrown. We took one of those bad runs, replayed it deterministically, bisected to the exact step where retrieval returned an irrelevant runbook, injected a corrected retrieval result, and showed the agent then produced the correct severity proposal. The final verdict — with full evidence trace — was automatically filed as a Jira issue. This is what AI reliability engineering looks like at the infrastructure level."

---

## 11. Key Research References

### Must-Cite in Pitch Deck

| Source | Key Takeaway | Link |
|---|---|---|
| **Anthropic — "Demystifying evals for AI agents"** (Jan 9, 2026) | Transcript vs. outcome; three grader types; multi-trial harness. Adopt this vocabulary verbatim. | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents |
| **τ-bench** (Yao et al., arXiv 2406.12045) | `pass^k` metric — GPT-4o: 61% pass@1 → 25% pass^8. DB-state outcome checking. | https://arxiv.org/abs/2406.12045 |
| **AgentRewardBench** (Lù et al., arXiv 2504.08942) | 1,302 annotated trajectories, 12 judges — position bias, length bias, reward hacking. | https://arxiv.org/abs/2504.08942 |
| **Agent-as-a-Judge** (Zhuge et al., arXiv 2508.02994) | Full-trajectory evaluation using agents as evaluators | https://arxiv.org/abs/2508.02994 |
| **AgentRR** (arXiv 2505.17716) | Record-and-replay for LLM agents; structured JSON plans for determinism | https://arxiv.org/abs/2505.17716 |
| **OTel GenAI Semantic Conventions** | Standard `gen_ai.*` spans; still experimental; covers MCP tool calls | https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/ |

### Libraries to Study

| Library | What to Learn From It | Link |
|---|---|---|
| llm-rewind | The HTTP proxy pattern for UC2 | https://pypi.org/project/llm-rewind/ |
| vcrpy | Cassette design for deterministic replay | https://github.com/kevin1024/vcrpy |
| langchain-replay | Decision vs. tool-result interception split | https://github.com/sixty-north/langchain-replay |
| OpenLLMetry | OTel-native LLM instrumentation — use this | https://github.com/traceloop/openllmetry |
| Langfuse | Self-hosted eval + trace store — use this | https://github.com/langfuse/langfuse |
| DeepEval | Built-in eval metrics for the grader library | https://github.com/confident-ai/deepeval |

### Atlassian Docs (Bookmark All of These)

| Resource | Link |
|---|---|
| Free cloud dev site | https://go.atlassian.com/cloud-dev |
| API token management | https://id.atlassian.com/manage-profile/security/api-tokens |
| Forge getting started | https://developer.atlassian.com/platform/forge/getting-started/ |
| Rovo Agent manifest | https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-agent/ |
| Forge Action reference | https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-action/ |
| Jira REST API v3 | https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/ |
| Confluence REST API | https://developer.atlassian.com/cloud/confluence/rest/v1/intro/ |
| JSM REST API | https://developer.atlassian.com/cloud/jira/service-desk/rest/intro/ |
| Atlassian MCP Server | https://mcp.atlassian.com/v1/mcp |
| Rate limiting (2026 model) | https://developer.atlassian.com/cloud/jira/platform/rate-limiting/ |

---

## 12. Judging Criteria → How We Win Each One

| Criterion | Weight | How We Win It |
|---|---|---|
| **Engineering Depth** | 50% | UC1+UC2 are infrastructure-layer AI engineering. Shared OTel GenAI trace spine. Judge calibration (position-bias test, pass^k). Hash-chained audit. This is not a chatbot — it is reliability infrastructure. |
| **Prototype Quality** | 25% | Synthetic data seeded before demo = no live surprises. Shared Azure dev env = consistent behavior. Cloudflare Tunnel = stable webhook URL that won't die mid-demo. No hardcoded values, no manual steps. |
| **Explainability & Auditability** | 15% | Every verdict: evidence per dimension + step attribution + confidence + self-critique + replay link. Hash-chained audit proves the log wasn't tampered with. A non-AI engineer can understand and act on every output. |
| **Evaluation & Rigour** | 10% | `pass^k` metric (τ-bench standard). Position-bias calibration (AgentRewardBench methodology). 100 synthetic incidents. Non-determinism explicitly addressed. |
| **Bonus: Protocol Gap** | ➕ | OTel replay extension + MCP audit trail published in `/spec` with reference implementations. Verifiable, real gaps. |
| **Bonus: Self-Evaluation** | ➕ | Judge outputs confidence + self-critique + auto-flag. Low-confidence verdicts auto-create Jira issue. Demo live. |
