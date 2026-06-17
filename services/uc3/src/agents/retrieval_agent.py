# services/uc3/src/agents/retrieval_agent.py
"""
Retrieval Agent — stub implementation.
Person B replaces _mock_search() with real Qdrant calls.
The public interface (retrieve method + return type) must not change.
"""
import os
from models import TicketContext, RetrievalResult, SimilarItem

# ── When Person B is ready, uncomment and install qdrant-client + sentence-transformers ──
# from qdrant_client import QdrantClient
# from sentence_transformers import SentenceTransformer
# _encoder = SentenceTransformer("all-MiniLM-L6-v2")
# _qdrant = QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=6333)


def _mock_search(query: str, collection: str, limit: int) -> list[SimilarItem]:
    """Returns empty results. Person B replaces this."""
    return []


class RetrievalAgent:
    def retrieve(self, ticket: TicketContext) -> RetrievalResult:
        query = f"{ticket.title}\n{ticket.description}\n{ticket.resolution}"

        # ── Swap these two blocks when Person B integrates Qdrant ──
        similar_tickets = _mock_search(query, "tickets", limit=3)
        similar_faqs = _mock_search(query, "faqs", limit=3)

        # Real Qdrant version (Person B):
        # vec = _encoder.encode(query).tolist()
        # hits_t = _qdrant.search("tickets", vec, limit=3)
        # hits_f = _qdrant.search("faqs", vec, limit=3)
        # similar_tickets = [SimilarItem(
        #     id=str(h.id), title=h.payload["title"],
        #     content_snippet=h.payload.get("content_snippet", "")[:400],
        #     similarity_score=h.score, url=h.payload.get("url", "")
        # ) for h in hits_t]
        # similar_faqs = [SimilarItem(...) for h in hits_f]

        top_faq_similarity = (
            max(f.similarity_score for f in similar_faqs) if similar_faqs else 0.0
        )

        return RetrievalResult(
            similar_tickets=similar_tickets,
            similar_faqs=similar_faqs,
            top_faq_similarity=top_faq_similarity,
        )
