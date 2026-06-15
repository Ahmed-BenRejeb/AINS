import sys, os, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TicketContext, RetrievalResult
from agents.reasoning_agent import ReasoningAgent

agent = ReasoningAgent()
empty_retrieval = RetrievalResult(similar_tickets=[], similar_faqs=[], top_faq_similarity=0.0)

y_true_worthy, y_pred_worthy = [], []
human_scores, model_scores = [], []

with open("src/data/test_tickets.csv") as f:
    for row in csv.DictReader(f):
        ticket = TicketContext(
            ticket_id=row["ticket_id"],
            title=row["title"],
            description=row["description"],
            resolution=row["resolution"],
            assignee="test",
            labels=[]
        )
        draft = agent.generate(ticket, empty_retrieval)
        print(f"{row['ticket_id']}: worthy={draft.faq_worthy} score={draft.clarity_score} | human: {row['faq_worthy']} {row['clarity_score']}")

        y_true_worthy.append(row["faq_worthy"].lower() == "true")
        y_pred_worthy.append(draft.faq_worthy)
        if row["clarity_score"]:
            human_scores.append(int(row["clarity_score"]))
            model_scores.append(draft.clarity_score)

from sklearn.metrics import accuracy_score, classification_report
from scipy.stats import pearsonr

print("\n=== FAQ-Worthiness ===")
print(classification_report(y_true_worthy, y_pred_worthy, target_names=["not worthy","worthy"]))

if human_scores:
    r, p = pearsonr(model_scores, human_scores)
    print(f"\n=== Clarity Correlation ===")
    print(f"Pearson r={r:.2f} p={p:.3f}")
