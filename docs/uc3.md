# AINS Hackathon – Work Division
## Use Case 3: JSM → Confluence FAQ Generator
**3 people · 10 days**

---

## Before You Split: Day 1–2 Together

Do these as a team before anyone goes parallel. An afternoon lost here saves two days of integration hell.

1. **Atlassian dev instance** — create a free Jira + Confluence cloud at [developer.atlassian.com](https://developer.atlassian.com). Generate API tokens for all three. This is the single most common blocker in Atlassian hackathons; do it first.
2. **Agree on and commit the shared data contracts** (see below). All three code against these from day 1.
3. **Repo skeleton** — `src/agents/`, `src/api/`, `src/retrieval/`, `src/evaluation/`, `docker-compose.yml`, `.env.example`, `README.md`.
4. **docker-compose up** — one command should start the API server + Qdrant. Target this by end of day 2.
5. **Test dataset** — Person C leads, all three contribute: 25–30 resolved JSM tickets (real or realistic synthetic) with manual labels: `faq_worthy` (yes/no), `clarity_score` (1–10 your honest judgment), `is_duplicate` (yes/no). Save as `data/test_tickets.csv`.
6. **Smoke tests**: A gets a webhook firing → B gets a first embedding working → C gets a Claude API call returning structured JSON. Just "hello world" for each path.

---

## Shared Data Contracts — Commit on Day 1

These Pydantic models are the handshake between every agent. No one changes them without agreement from the other two.

```python
# src/models.py

from pydantic import BaseModel

class TicketContext(BaseModel):
    ticket_id: str
    title: str
    description: str
    resolution: str
    assignee: str
    labels: list[str]

class SimilarItem(BaseModel):
    id: str
    title: str
    content_snippet: str   # max 400 tokens — B enforces this
    similarity_score: float
    url: str

class RetrievalResult(BaseModel):
    similar_tickets: list[SimilarItem]   # top-3
    similar_faqs: list[SimilarItem]      # top-3
    top_faq_similarity: float            # highest score among similar_faqs

class FAQDraft(BaseModel):
    faq_worthy: bool
    faq_worthy_reason: str
    problem_statement: str
    root_cause: str
    solution_steps: list[str]
    clarity_score: int                   # 1–10
    missing_explanations: str            # what a reviewer should add
    duplicate_flag: bool
    duplicate_faq_url: str | None

class PublishingDecision(BaseModel):
    action: str  # "reject" | "link_duplicate" | "auto_publish" | "draft_review" | "escalate"
    confluence_page_url: str | None
    jsm_comment: str | None
    escalation_note: str | None

class TraceEvent(BaseModel):
    run_id: str
    step: str               # "retrieval" | "reasoning" | "publishing"
    timestamp: str
    input_snapshot: dict
    output_snapshot: dict
    latency_ms: int
    model: str | None
    tokens_used: int | None
```

---

## Person A — Backend & Orchestration

### Role
You are the spine of the system. Every request flows through your code. You own the trigger, the coordination, the Atlassian API clients, and the UC2 tracer. Person B and C build agents; you wire them together and make sure every step is logged.

### Agents you own
**Orchestrator Agent** — not an LLM agent, but the async Python function that receives a resolved ticket and calls Retrieval → Reasoning → Publishing in sequence, handling errors at each step.

**UC2 Tracer** — an interceptor layer wrapping every agent call. Before/after each step, it serialises `TraceEvent` to SQLite. This is your bonus points and your demo story: "we can replay any execution exactly."

### Tech stack
- **FastAPI** + uvicorn — the webhook endpoint and any internal REST surface
- **httpx** — async HTTP client for all Atlassian API calls
- **atlassian-python-api** — or roll raw httpx calls for Jira + Confluence REST APIs
- **SQLite** + aiosqlite — trace store (simple, zero setup, human-inspectable)
- **python-dotenv** — config management
- **docker-compose** — bring up the whole system with one command

### Tasks

**Days 1–2 (foundation)**
- Scaffold the FastAPI app with a `POST /webhook` endpoint that parses a JSM `issue_updated` event and extracts ticket details into `TicketContext`
- Verify you can call `GET /rest/api/3/issue/{issueId}` and get ticket body, resolution, assignee
- Write `src/atlassian/jira_client.py` and `src/atlassian/confluence_client.py` with these methods:

```python
# jira_client.py
async def get_ticket(ticket_id: str) -> TicketContext
async def post_comment(ticket_id: str, body: str) -> None

# confluence_client.py
async def create_page(space_key: str, title: str, body_html: str) -> str  # returns page URL
async def create_draft(space_key: str, title: str, body_html: str, reviewer: str) -> str
async def link_existing_faq(ticket_id: str, faq_url: str) -> None
```

- Build a `MockAtlassianClient` that returns fixture data — B and C need this to test without real credentials.

**Days 3–5 (build)**
- Implement `OrchestratorAgent.run(ticket: TicketContext) -> PublishingDecision`:
  1. Call `RetrievalAgent.retrieve(ticket)` — B's interface
  2. Call `ReasoningAgent.generate(ticket, retrieval_result)` — C's interface
  3. Call `PublishingAgent.decide(draft)` — C's interface
  4. Execute the publishing action using the Atlassian clients
  5. Wrap each call in the UC2 tracer
- Implement `Tracer`:
  - `trace_call(step, fn, input)` — calls `fn(input)`, records `TraceEvent` before and after
  - `get_trace(run_id)` — returns full execution trace for a given run
  - `replay(run_id)` — re-runs the orchestrator using recorded inputs (mock-intercepts the LLM and tool calls)

**Days 6–7 (integration)**
- Wire B's `RetrievalAgent` and C's `ReasoningAgent` + `PublishingAgent` into the orchestrator
- Run 5 end-to-end tests with real tickets
- Handle and log failure cases: Atlassian API timeout, agent returning `faq_worthy=False`, retrieval returning empty results

**Days 8–9 (polish + demo prep)**
- Build a simple `GET /trace/{run_id}` endpoint that returns the full execution trace as JSON — this is your UC2 demo
- Confirm `POST /webhook` handles the exact Jira event payload format (test with a real Jira automation webhook)
- Write the architecture diagram for the pitch deck

### What done looks like
A ticket resolved in Jira triggers the webhook → the full pipeline runs → a Confluence page is created (or a JSM comment is posted) → the trace is stored and retrievable via API. No manual steps.

---

## Person B — Retrieval & Data

### Role
You are the memory of the system. You index everything the company already knows — resolved tickets, existing FAQs — and give the Reasoning Agent the context it needs to avoid writing duplicate content and to produce grounded FAQs. Your retrieval quality directly determines the quality of Person C's output.

### Agents you own
**Retrieval Agent** — given a new ticket, search both indexed collections and return `RetrievalResult`. Enforces the 400-token context budget per item so the Reasoning Agent's prompt stays manageable.

**Indexing Pipeline** — a one-time (and schedulable) script that crawls JSM for resolved tickets and Confluence for existing FAQ pages, embeds them, and upserts them into Qdrant.

### Tech stack
- **Qdrant** — vector database, run locally via Docker
- **sentence-transformers** — `all-MiniLM-L6-v2` for embeddings (384 dims, fast, free, runs CPU). If your demo tickets are in French, switch to `paraphrase-multilingual-MiniLM-L12-v2`
- **tiktoken** — count tokens before passing content to the Reasoning Agent
- **pandas** — manage the test dataset CSV
- **httpx** — if you crawl Confluence to build the index

### Tasks

**Days 1–2 (foundation)**
- Run Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
- Create two collections:
  ```python
  # tickets collection
  {"name": "tickets", "vectors": {"size": 384, "distance": "Cosine"}}
  # faqs collection
  {"name": "faqs", "vectors": {"size": 384, "distance": "Cosine"}}
  ```
- Write `embed(text: str) -> list[float]` using sentence-transformers — test it works
- Write a small script that loads 10 fixture tickets from JSON and indexes them — by end of day 2, you should be able to run a search query and get back results

**Days 3–5 (build)**
- Build `src/retrieval/indexer.py`:
  - `index_ticket(ticket: dict)` — embeds `title + description + resolution`, stores with payload `{ticket_id, title, url, assignee, labels}`
  - `index_faq(faq: dict)` — embeds `title + body_text`, stores with payload `{page_id, title, url, space}`
  - `build_full_index()` — crawls JSM and Confluence via their APIs to index everything
- Build `src/agents/retrieval_agent.py`:
  ```python
  class RetrievalAgent:
      def retrieve(self, ticket: TicketContext) -> RetrievalResult:
          query = f"{ticket.title}\n{ticket.description}\n{ticket.resolution}"
          query_vec = embed(query)
          
          tickets = qdrant.search("tickets", query_vec, limit=3)
          faqs = qdrant.search("faqs", query_vec, limit=3)
          
          # Enforce 400-token content budget per item
          return RetrievalResult(
              similar_tickets=[to_similar_item(t, budget=400) for t in tickets],
              similar_faqs=[to_similar_item(f, budget=400) for f in faqs],
              top_faq_similarity=faqs[0].score if faqs else 0.0
          )
  ```
- **Important:** the `top_faq_similarity` field is what Person C uses for duplicate detection. If this score > 0.88, the FAQ probably already exists. Validate this threshold against your test dataset — find 5-10 known duplicates and see what score they get.

**Days 6–7 (integration)**
- Plug the `RetrievalAgent` into A's orchestrator via the agreed interface
- Test retrieval on the 25-ticket evaluation set — spot-check that the returned similar items are genuinely related
- Tune: if you're getting bad results, try indexing `title + description` only (without resolution), since resolution text can dominate the embedding

**Days 8–9 (eval support)**
- Help C run the duplicate detection evaluation: for each test ticket marked `is_duplicate=true`, confirm that `top_faq_similarity` is above threshold
- Document: which embedding model, which similarity metric, what threshold, why

### What done looks like
Call `retrieval_agent.retrieve(ticket)` with any ticket and get back 3 semantically similar past tickets + 3 existing FAQs with similarity scores, each trimmed to fit within the context budget.

---

## Person C — AI Core & Evaluation

### Role
You are the brain and the judge. You build the two agents that do the actual reasoning, and you also run the evaluation that proves the system works. Your work touches the most visible part of the demo — the generated FAQ — so prompt quality and structured output reliability matter most.

### Agents you own
**Reasoning + Quality Agent** — the main LLM call. Takes `TicketContext + RetrievalResult` and produces a complete `FAQDraft` including the clarity score and duplicate flag.

**Publishing Agent** — a deterministic Python decision tree (not an LLM). Takes `FAQDraft` and returns `PublishingDecision` with the right action.

### Tech stack
- **anthropic** Python SDK — `claude-sonnet-4-6` for the main generation call
- **Pydantic** — enforce the `FAQDraft` schema via Claude's tool-use / structured output
- **Jinja2** — prompt templates (keep prompts in `.j2` files, not hardcoded strings)
- **scikit-learn** — precision, recall, F1 for evaluation metrics
- **pandas** — evaluation data management
- **Rich** — clean terminal output for the demo walkthrough

### Tasks

**Days 1–2 (foundation)**
- Get a Claude API key, make a test call that takes a raw ticket description and returns a JSON FAQ. Don't worry about structure yet — just see what the model produces naturally.
- Start building the 25-30 ticket test dataset with A and B. Write the labels yourself; this takes a few hours but is the most important thing you do for the evaluation.

**Days 3–5 (build)**

Build `src/agents/reasoning_agent.py`. The prompt is the core engineering artifact here:

```python
SYSTEM_PROMPT = """
You are an expert technical writer who transforms resolved support tickets into public-facing FAQ entries.

You will receive:
- A resolved support ticket (title, description, resolution)
- Up to 3 semantically similar past tickets for context
- Up to 3 existing FAQ pages that may already cover this issue

Your job is to call the `generate_faq_draft` tool with a complete, structured FAQ draft.

Rules:
- If the ticket is too narrow, internal, or sensitive to be a public FAQ (e.g. specific to one user, contains PII, or a one-off incident), set faq_worthy=false.
- The problem_statement must be written in plain language a non-technical user would understand.
- The root_cause may be more technical, but must still be readable.
- solution_steps must be numbered and actionable — no vague instructions like "contact support".
- clarity_score: rate 1–10. 8+ means auto-publishable as-is. 5–7 needs human review. Below 5 needs significant rework.
- clarity_score rubric: 10=complete, clear, no jargon, verified steps. 7=mostly clear but missing one element. 5=draft quality, needs work. 3=thin or ambiguous. 1=insufficient information to write a FAQ.
- duplicate_flag: set true only if top_faq_similarity > 0.88 AND the existing FAQ genuinely covers the same problem.
"""

USER_TEMPLATE = """
## Resolved ticket
Title: {{ ticket.title }}
Description: {{ ticket.description }}
Resolution: {{ ticket.resolution }}

## Similar past tickets (context only)
{% for t in retrieval.similar_tickets %}
[{{ t.similarity_score:.2f }}] {{ t.title }}: {{ t.content_snippet }}
{% endfor %}

## Existing FAQs that may be related
{% for f in retrieval.similar_faqs %}
[{{ f.similarity_score:.2f }}] {{ f.title }}: {{ f.content_snippet }}
{% endfor %}
"""
```

Use Claude's tool-use to enforce `FAQDraft` output — do not use free-form JSON parsing:
```python
tools = [{
    "name": "generate_faq_draft",
    "description": "Generate a structured FAQ draft from the resolved ticket",
    "input_schema": FAQDraft.model_json_schema()
}]
```

Build `src/agents/publishing_agent.py` — pure Python, no LLM:
```python
class PublishingAgent:
    def decide(self, draft: FAQDraft) -> PublishingDecision:
        if not draft.faq_worthy:
            return PublishingDecision(
                action="reject",
                jsm_comment=f"This ticket was reviewed for FAQ publication but was not selected because: {draft.faq_worthy_reason}"
            )
        if draft.duplicate_flag and draft.duplicate_faq_url:
            return PublishingDecision(
                action="link_duplicate",
                confluence_page_url=draft.duplicate_faq_url,
                jsm_comment=f"A FAQ covering this issue already exists: {draft.duplicate_faq_url}"
            )
        if draft.clarity_score >= 8:
            return PublishingDecision(action="auto_publish")
        elif draft.clarity_score >= 5:
            return PublishingDecision(
                action="draft_review",
                escalation_note=f"Clarity score: {draft.clarity_score}/10. Missing: {draft.missing_explanations}"
            )
        else:
            return PublishingDecision(
                action="escalate",
                escalation_note=f"Score {draft.clarity_score}/10 — needs significant rework. {draft.missing_explanations}"
            )
```

**Days 6–7 (integration)**
- Plug into A's orchestrator — confirm your agents receive the correct types and return valid models
- Run 5 end-to-end tests and read the generated FAQs. Fix whatever looks wrong (usually the solution_steps are too vague or the problem_statement is too technical).
- Adjust the clarity rubric in the system prompt if the model's scores don't match your human labels.

**Days 8–9 (evaluation + pitch)**

Run your evaluation on the 25-ticket test set. You need to report three metrics:

**Metric 1 — FAQ-worthiness accuracy**
Compare `draft.faq_worthy` against your manual labels. Report accuracy, precision, recall. Target: accuracy > 80%.
```python
from sklearn.metrics import classification_report
print(classification_report(y_true, y_pred, target_names=["not worthy", "worthy"]))
```

**Metric 2 — Clarity score calibration**
Compute Pearson correlation between `draft.clarity_score` and your manual scores for the 10–15 tickets you labeled. A correlation > 0.7 is a good result to present.
```python
from scipy.stats import pearsonr
r, p = pearsonr(model_scores, human_scores)
```

**Metric 3 — Duplicate detection accuracy**
On the tickets you labeled `is_duplicate=true`, check whether `duplicate_flag=true` and `top_faq_similarity > 0.88`. Report precision/recall.

Write these results up in `evaluation/report.md` — one page, three tables, methodology paragraph. This goes into the final submission.

Lead the pitch deck (15 slides). Cover: problem, why AI is necessary (show the IF/THEN rule failure), architecture, the 5 publishing paths, demo walkthrough, evaluation results, limitations, next steps.

### What done looks like
Call `reasoning_agent.generate(ticket, retrieval_result)` with any ticket and get a complete `FAQDraft` in under 8 seconds. The `publishing_agent.decide(draft)` returns the correct action for every test case. The evaluation report shows measurable, honest results.

---

## Shared Timeline

| Days | A | B | C |
|------|---|---|---|
| 1–2 | FastAPI skeleton + first Atlassian API call | Qdrant running + first embedding | First Claude API call + test dataset started |
| 3–5 | Orchestrator + Tracer + Atlassian clients | Indexing pipeline + Retrieval Agent | Reasoning Agent + Publishing Agent |
| 6 | **Integration day** — wire all three agents end-to-end, fix data contract mismatches | Fix retrieval quality issues | Fix prompt issues from integration tests |
| 7–8 | Edge cases + UC2 replay demo | Threshold validation against test set | Evaluation runs + report |
| 9 | Architecture diagram + README polish | Indexing final test data | Pitch deck + demo video |
| 10 | Buffer / submit | Buffer / submit | Buffer / submit |

---

## Integration Contracts

These are the exact function signatures A depends on from B and C. Don't break them after day 2.

```python
# From Person B — src/agents/retrieval_agent.py
class RetrievalAgent:
    def retrieve(self, ticket: TicketContext) -> RetrievalResult: ...

# From Person C — src/agents/reasoning_agent.py
class ReasoningAgent:
    def generate(self, ticket: TicketContext, context: RetrievalResult) -> FAQDraft: ...

# From Person C — src/agents/publishing_agent.py
class PublishingAgent:
    def decide(self, draft: FAQDraft) -> PublishingDecision: ...
```

If B or C needs to change a signature, they discuss it with A first and update `src/models.py` as a committed change.

---

## Evaluation Test Dataset Format

Save as `data/test_tickets.csv`. All three build this together on day 1–2.

```csv
ticket_id, title, description, resolution, faq_worthy, clarity_score, is_duplicate, notes
PROJ-1, "Cannot login after password reset", "...", "...", true, 8, false, "classic FAQ candidate"
PROJ-2, "User John's VPN dropped once", "...", "...", false, 3, false, "too specific"
PROJ-3, "Email notifications not sending", "...", "...", true, 6, true, "duplicate of CONF-145"
...
```

You need at least: 10 clear FAQ candidates, 5 not-worthy tickets, 5 duplicates of existing FAQs, 5 edge cases. Aim for 25–30 total.

---

## What to Demo on Day 10

Walk through one full end-to-end scenario live:

1. Show a resolved JSM ticket (real or synthetic) on screen
2. Trigger the webhook — either manually via `curl` or by resolving a real Jira ticket
3. Show the logs as the pipeline runs (Orchestrator → Retrieval → Reasoning → Publishing)
4. Show the generated Confluence FAQ page (or JSM comment, depending on the decision)
5. Open the trace endpoint (`GET /trace/{run_id}`) and show the full execution log — this is your UC2 bonus point
6. Show the evaluation report — two slides, three metrics

Prepare one scenario for each publishing path (auto-publish, draft-review, and reject) so you can switch if something breaks live.
