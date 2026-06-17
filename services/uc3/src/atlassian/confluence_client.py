import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class ConfluenceClient:
    def __init__(self):
        self.base_url = os.getenv("ATLASSIAN_BASE_URL")
        self.space_key = os.getenv("CONFLUENCE_SPACE_KEY", "FAQ")
        self.auth = HTTPBasicAuth(
            os.getenv("ATLASSIAN_EMAIL"),
            os.getenv("ATLASSIAN_API_TOKEN")
        )

    def _page_exists(self, title: str) -> tuple[bool, str | None]:
        url = f"{self.base_url}/wiki/rest/api/content"
        params = {
            "spaceKey": self.space_key,
            "title": title,
            "type": "page"
        }
        try:
            r = requests.get(url, params=params, auth=self.auth, timeout=10)
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                page_id = results[0]["id"]
                return True, f"{self.base_url}/wiki/spaces/{self.space_key}/pages/{page_id}"
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            pass
        return False, None

    def create_page(self, title: str, body_html: str) -> tuple[bool, str]:
        exists, existing_url = self._page_exists(title)
        if exists:
            print(f"[ConfluenceClient] Page already exists: {existing_url}")
            return True, existing_url
        
        url = f"{self.base_url}/wiki/rest/api/content"
        
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": self.space_key},
            "body": {
                "storage": {
                    "value": body_html, 
                    "representation": "storage"
                }
            }
        }
        
        try:
            r = requests.post(url, json=payload, auth=self.auth, timeout=10)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[ConfluenceClient] Could not create page (network error: {type(e).__name__})")
            raise
        
        if r.status_code == 400:
            print(f"DEBUG: Payload causing 400: {json.dumps(payload, indent=2)}")
            print(f"DEBUG: Server Response: {r.text}")
            
        r.raise_for_status()
        
        page_id = r.json()["id"]
        return False, f"{self.base_url}/wiki/spaces/{self.space_key}/pages/{page_id}"
    def create_draft(self, title: str, body_html: str) -> str:
        url = f"{self.base_url}/wiki/rest/api/content"
        payload = {
            "type": "page",
            "status": "draft",
            "title": title,
            "space": {"key": self.space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}}
        }
        try:
            r = requests.post(url, json=payload, auth=self.auth, timeout=10)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[ConfluenceClient] Could not create draft (network error: {type(e).__name__})")
            raise
        r.raise_for_status()
        page_id = r.json()["id"]
        return f"{self.base_url}/wiki/spaces/{self.space_key}/pages/{page_id}"
