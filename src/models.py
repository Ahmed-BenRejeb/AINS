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
    content_snippet: str
    similarity_score: float
    url: str

class RetrievalResult(BaseModel):
    similar_tickets: list[SimilarItem]
    similar_faqs: list[SimilarItem]
    top_faq_similarity: float

class FAQDraft(BaseModel):
    faq_worthy: bool
    faq_worthy_reason: str
    problem_statement: str
    root_cause: str
    solution_steps: list[str]
    clarity_score: int
    missing_explanations: str
    duplicate_flag: bool
    duplicate_faq_url: str | None

class PublishingDecision(BaseModel):
    action: str  # "reject" | "link_duplicate" | "auto_publish" | "draft_review" | "escalate"
    confluence_page_url: str | None = None
    jsm_comment: str | None = None
    escalation_note: str | None = None
