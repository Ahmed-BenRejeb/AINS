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

        prompt = f"""You are a strict technical writer deciding whether a resolved support ticket should become a public FAQ entry.

RESOLVED TICKET:
Title: {ticket.title}
Description: {ticket.description}
Resolution: {ticket.resolution}

SIMILAR PAST TICKETS (context only):
{similar_tickets_text}

EXISTING FAQS THAT MAY OVERLAP:
{similar_faqs_text}

Top FAQ similarity score: {context.top_faq_similarity:.2f}

=== WORTHINESS RULES (read carefully) ===

Set faq_worthy=FALSE in ANY of these cases — do not override this:
- The resolution was a one-off manual action (e.g. "IT updated permissions manually", "applied emergency extension", "pushed software remotely for this user")
- The ticket is specific to a named individual or a single user's account state
- The resolution required internal access that another user could not reproduce themselves
- The issue was caused by a policy or administrative decision, not a reproducible technical problem
- The ticket contains no generalizable lesson — another user with the same symptom would need different steps

Set faq_worthy=TRUE only if:
- The same problem could affect multiple different users
- The resolution steps are reproducible without IT intervention, OR the FAQ explains clearly when to escalate and why
- The problem and solution can be written without referencing any specific user

=== CLARITY SCORE RUBRIC ===
10 = complete, clear, no jargon, verified steps anyone can follow
8-9 = mostly complete, minor gaps, auto-publishable
5-7 = draft quality, one or more steps vague or missing, needs human review  
3-4 = thin or ambiguous, significant rework needed
1-2 = insufficient information to write a FAQ at all

=== DUPLICATE RULE ===
Set duplicate_flag=true ONLY if top_faq_similarity > 0.88 AND the existing FAQ genuinely covers the same problem and solution.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object with these exact fields, no other text:
{{
  "faq_worthy": <true or false>,
  "faq_worthy_reason": "<one sentence explaining why worthy or not worthy>",
  "problem_statement": "<plain language problem a non-technical user would understand, or empty string if not worthy>",
  "root_cause": "<technical explanation, or empty string if not worthy>",
  "solution_steps": ["<step 1>", "<step 2>"],
  "clarity_score": <integer 1-10>,
  "missing_explanations": "<what a reviewer should add, or 'none' if complete>",
  "duplicate_flag": <true or false>,
  "duplicate_faq_url": <"url" or null>
}}"""

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return FAQDraft.model_validate_json(response.choices[0].message.content)
