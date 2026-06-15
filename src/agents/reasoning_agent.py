import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from src.models import TicketContext, RetrievalResult, FAQDraft

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=FAQDraft
    )
)

class ReasoningAgent:
    def generate(self, ticket: TicketContext, context: RetrievalResult) -> FAQDraft:
        prompt = f"""
You are a technical writer transforming resolved support tickets into public FAQ entries.

RESOLVED TICKET:
Title: {ticket.title}
Description: {ticket.description}
Resolution: {ticket.resolution}

SIMILAR PAST TICKETS (for context):
{self._format_similar(context.similar_tickets)}

EXISTING FAQS THAT MAY OVERLAP:
{self._format_similar(context.similar_faqs)}
Top FAQ similarity score: {context.top_faq_similarity:.2f}

Rules:
- faq_worthy=false if ticket is too specific to one user, contains PII, or a one-off incident
- problem_statement must be plain language any user understands
- solution_steps must be numbered and actionable, never "contact support"
- clarity_score 1-10: 8+ = auto-publish, 5-7 = needs review, below 5 = rework needed
- duplicate_flag=true only if top_faq_similarity > 0.88 AND existing FAQ covers the same issue
"""
        response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=FAQDraft,
    )
)
        return FAQDraft.model_validate_json(response.text)

    def _format_similar(self, items):
        if not items:
            return "None found."
        return "\n".join(
            f"[{item.similarity_score:.2f}] {item.title}: {item.content_snippet}"
            for item in items
        )
