import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

class ConfluenceClient:
    def __init__(self):
        self.base_url = os.getenv("ATLASSIAN_BASE_URL")
        self.space_key = os.getenv("CONFLUENCE_SPACE_KEY", "FAQ")
        self.auth = HTTPBasicAuth(
            os.getenv("ATLASSIAN_EMAIL"),
            os.getenv("ATLASSIAN_API_TOKEN")
        )

    def create_page(self, title: str, body_html: str) -> str:
        url = f"{self.base_url}/wiki/rest/api/content"
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}}
        }
        r = requests.post(url, json=payload, auth=self.auth)
        r.raise_for_status()
        page_id = r.json()["id"]
        return f"{self.base_url}/wiki/spaces/{self.space_key}/pages/{page_id}"

    def create_draft(self, title: str, body_html: str) -> str:
        url = f"{self.base_url}/wiki/rest/api/content"
        payload = {
            "type": "page",
            "status": "draft",
            "title": title,
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}}
        }
        r = requests.post(url, json=payload, auth=self.auth)
        r.raise_for_status()
        page_id = r.json()["id"]
        return f"{self.base_url}/wiki/spaces/{self.space_key}/pages/{page_id}"
