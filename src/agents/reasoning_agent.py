import os
import json
from groq import Groq
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TicketContext, RetrievalResult, FAQDraft

load_dotenv()

class ReasoningAgent:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def generate(self, ticket: TicketContext, context: RetrievalResult) -> FAQDraft:
        similar_tickets_text = "\n".join(
            f"[{t.similarity_score:.2f}] {t.title}: {t.content_snippet}"
            for t in context.similar_tickets
        ) or "None found."

        similar_faqs_text = "\n".join(
            f"[{f.similarity_score:.2f}] {f.title}: {f.content_snippet}"
            for f in context.similar_faqs
        ) or "None found."

        prompt = f"""You are a technical writer transforming resolved support tickets into public FAQ entries.

RESOLVED TICKET:
Title: {ticket.title}
Description: {ticket.description}
Resolution: {ticket.resolution}

SIMILAR PAST TICKETS (context only):
{similar_tickets_text}

EXISTING FAQS THAT MAY OVERLAP:
{similar_faqs_text}
Top FAQ similarity score: {context.top_faq_similarity:.2f}

Rules:
- Set faq_worthy=false if the ticket is too specific to one user, contains PII, or is a one-off incident
- problem_statement must be in plain language a non-technical user would understand
- solution_steps must be numbered and actionable, never just "contact support"
- clarity_score 1-10: 8+ means auto-publishable, 5-7 needs review, below 5 needs rework
- Set duplicate_flag=true ONLY if top_faq_similarity > 0.88 AND an existing FAQ covers the same issue

Return ONLY a JSON object with these exact fields:
{{
  "faq_worthy": true,
  "faq_worthy_reason": "explanation",
  "problem_statement": "plain language problem",
  "root_cause": "technical explanation",
  "solution_steps": ["step 1", "step 2"],
  "clarity_score": 8,
  "missing_explanations": "what's missing or none",
  "duplicate_flag": false,
  "duplicate_faq_url": null
}}"""

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return FAQDraft.model_validate_json(response.choices[0].message.content)
