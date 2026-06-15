import os
import json
from groq import Groq
from dotenv import load_dotenv
from models import FAQDraft

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

prompt = """
You are a technical writer creating FAQ entries from resolved support tickets.

RESOLVED TICKET:
Title: Cannot login after password reset
Description: User tried resetting password but the link expired after 48 hours.
Resolution: Password reset tokens expire in 24 hours. Issued a new link and user logged in successfully.

Return ONLY a JSON object with these exact fields:
{
  "faq_worthy": true or false,
  "faq_worthy_reason": "why or why not",
  "problem_statement": "plain language description for non-technical users",
  "root_cause": "technical explanation",
  "solution_steps": ["step 1", "step 2", "step 3"],
  "clarity_score": 8,
  "missing_explanations": "what's missing or 'none'",
  "duplicate_flag": false,
  "duplicate_faq_url": null
}
"""

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.1,
)

raw = response.choices[0].message.content
draft = FAQDraft.model_validate_json(raw)

print(f"FAQ Worthy: {draft.faq_worthy}")
print(f"Problem: {draft.problem_statement}")
print(f"Clarity Score: {draft.clarity_score}/10")
print("Steps:")
for i, step in enumerate(draft.solution_steps, 1):
    print(f"  {i}. {step}")
