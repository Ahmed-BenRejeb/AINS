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
