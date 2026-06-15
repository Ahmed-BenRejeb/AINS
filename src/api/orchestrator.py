import sys, os, json, sqlite3, uuid
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TicketContext, RetrievalResult, SimilarItem, FAQDraft, PublishingDecision
from agents.reasoning_agent import ReasoningAgent
from agents.publishing_agent import PublishingAgent
from atlassian.jira_client import JiraClient
from atlassian.confluence_client import ConfluenceClient

# Simple mock retrieval until Person B's Qdrant is ready
def mock_retrieval(ticket: TicketContext) -> RetrievalResult:
    return RetrievalResult(similar_tickets=[], similar_faqs=[], top_faq_similarity=0.0)

def init_db():
    conn = sqlite3.connect("traces.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS traces (
        run_id TEXT, step TEXT, timestamp TEXT,
        input_json TEXT, output_json TEXT, latency_ms INTEGER
    )""")
    conn.commit()
    return conn

def log_trace(conn, run_id, step, input_data, output_data, latency_ms):
    conn.execute("INSERT INTO traces VALUES (?,?,?,?,?,?)", (
        run_id, step, datetime.utcnow().isoformat(),
        json.dumps(input_data), json.dumps(output_data), latency_ms
    ))
    conn.commit()

def run_pipeline(ticket_id: str):
    conn = init_db()
    run_id = str(uuid.uuid4())
    jira = JiraClient()
    confluence = ConfluenceClient()
    reasoning = ReasoningAgent()
    publishing = PublishingAgent()

    import time

    # Step 1: Fetch ticket
    t0 = time.time()
    ticket = jira.get_ticket(ticket_id)
    log_trace(conn, run_id, "fetch_ticket", {"ticket_id": ticket_id}, ticket.model_dump(), int((time.time()-t0)*1000))

    # Step 2: Retrieval (mock for now, swap with Person B's agent later)
    t0 = time.time()
    retrieval = mock_retrieval(ticket)
    log_trace(conn, run_id, "retrieval", ticket.model_dump(), retrieval.model_dump(), int((time.time()-t0)*1000))

    # Step 3: Generate FAQ draft
    t0 = time.time()
    draft = reasoning.generate(ticket, retrieval)
    log_trace(conn, run_id, "reasoning", retrieval.model_dump(), draft.model_dump(), int((time.time()-t0)*1000))

    # Step 4: Publishing decision
    t0 = time.time()
    decision = publishing.decide(draft)
    log_trace(conn, run_id, "publishing_decision", draft.model_dump(), decision.model_dump(), int((time.time()-t0)*1000))

    # Step 5: Execute
    if decision.action == "auto_publish":
        html = f"<h2>Problem</h2><p>{draft.problem_statement}</p><h2>Root Cause</h2><p>{draft.root_cause}</p><h2>Solution</h2><ol>{''.join(f'<li>{s}</li>' for s in draft.solution_steps)}</ol>"
        url = confluence.create_page(ticket.title, html)
        jira.post_comment(ticket_id, f"FAQ auto-published: {url}")
        decision.confluence_page_url = url
        print(f"✅ Auto-published: {url}")
    elif decision.action == "draft_review":
        html = f"<h2>Problem</h2><p>{draft.problem_statement}</p><h2>Root Cause</h2><p>{draft.root_cause}</p><h2>Solution</h2><ol>{''.join(f'<li>{s}</li>' for s in draft.solution_steps)}</ol>"
        url = confluence.create_draft(ticket.title, html)
        jira.post_comment(ticket_id, f"FAQ draft created for review (score {draft.clarity_score}/10): {url}")
        print(f"📝 Draft created: {url}")
    elif decision.action == "reject":
        jira.post_comment(ticket_id, decision.jsm_comment or "Ticket not suitable for FAQ.")
        print(f"❌ Rejected: {draft.faq_worthy_reason}")
    elif decision.action == "link_duplicate":
        jira.post_comment(ticket_id, decision.jsm_comment or "Duplicate FAQ exists.")
        print(f"🔗 Duplicate: {decision.confluence_page_url}")

    log_trace(conn, run_id, "execute", decision.model_dump(), {"done": True}, 0)
    print(f"\nRun ID: {run_id}")
    return run_id

if __name__ == "__main__":
    import sys
    ticket_id = sys.argv[1] if len(sys.argv) > 1 else "AINS-1"
    run_pipeline(ticket_id)
