import os
import csv
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TicketContext
load_dotenv()

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test_tickets.csv")

def _load_from_csv(ticket_id: str) -> TicketContext | None:
    if not os.path.exists(CSV_PATH):
        return None
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            if row["ticket_id"] == ticket_id:
                return TicketContext(
                    ticket_id=row["ticket_id"],
                    title=row["title"],
                    description=row["description"],
                    resolution=row["resolution"],
                    assignee="test",
                    labels=[]
                )
    return None

class JiraClient:
    def __init__(self):
        self.base_url = os.getenv("ATLASSIAN_BASE_URL")
        self.auth = HTTPBasicAuth(
            os.getenv("ATLASSIAN_EMAIL"),
            os.getenv("ATLASSIAN_API_TOKEN")
        )

    def get_ticket(self, ticket_id: str) -> TicketContext:
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}"
        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
            data = r.json()
            fields = data["fields"]
            return TicketContext(
                ticket_id=ticket_id,
                title=fields.get("summary", ""),
                description=self._extract_text(fields.get("description")),
                resolution=self._extract_text(fields.get("resolution")),
                assignee=fields.get("assignee", {}).get("displayName", "unassigned") if fields.get("assignee") else "unassigned",
                labels=fields.get("labels", [])
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                ticket = _load_from_csv(ticket_id)
                if ticket:
                    print(f"[JiraClient] {ticket_id} not found in Jira — loaded from local CSV")
                    return ticket
            raise

    def post_comment(self, ticket_id: str, body: str) -> None:
        url = f"{self.base_url}/rest/api/3/issue/{ticket_id}/comment"
        payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}}
        try:
            requests.post(url, json=payload, auth=self.auth)
        except Exception:
            print(f"[JiraClient] Could not post comment to {ticket_id} (not in Jira)")

    def _extract_text(self, field) -> str:
        if not field:
            return ""
        if isinstance(field, str):
            return field
        if isinstance(field, dict) and "content" in field:
            texts = []
            for block in field["content"]:
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
            return " ".join(texts)
        return str(field)
