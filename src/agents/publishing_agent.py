import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import FAQDraft, PublishingDecision

class PublishingAgent:
    def decide(self, draft: FAQDraft) -> PublishingDecision:
        if not draft.faq_worthy:
            return PublishingDecision(
                action="reject",
                jsm_comment=f"This ticket was reviewed for FAQ publication but not selected because: {draft.faq_worthy_reason}"
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
