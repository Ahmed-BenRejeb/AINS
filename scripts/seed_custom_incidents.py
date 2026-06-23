#!/usr/bin/env python3
"""seed_custom_incidents.py — seed an enterprise's own incidents for a tailored demo.

Reads a CSV of incidents (the demo company's own wording), creates each as a Jira
issue in the AO project, embeds it with Cloudflare Workers AI BGE-Base-EN (768-dim),
and upserts the vector into the xqdrant ``incidents`` collection — so ``/analyze``
retrieves *their* incidents and the RCAs feel "about them" instead of the generic
seed data.

CSV format (header row required); ``category`` is optional::

    summary,description,category
    Checkout API 5xx spike,"Payment service returning 502 under load, pool saturated",database
    Search latency regression,"p99 search latency 4x after the 14:00 deploy",performance

Usage::

    set -a; source /srv/sentinel/.env; set +a
    uv run python scripts/seed_custom_incidents.py --csv my_incidents.csv
    uv run python scripts/seed_custom_incidents.py --csv my_incidents.csv --dry-run

Idempotency: each xqdrant point id is a UUIDv5 of the created Jira key, so the
vector tracks the issue. Re-running the CSV creates new Jira issues (Jira has no
natural upsert), so run it once per dataset.

Reads from the environment (already in ``.env.example``): ``ATLASSIAN_SITE``,
``ATLASSIAN_EMAIL``, ``ATLASSIAN_API_TOKEN``, ``ATLASSIAN_JIRA_PROJECT_KEY``,
``CLOUDFLARE_ACCOUNT_ID``, ``CLOUDFLARE_API_TOKEN``, ``CF_AI_MODEL_EMBED``,
``XQDRANT_URL``, ``XQDRANT_INCIDENTS_COLLECTION``.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import uuid

import httpx

EMBED_MODEL = os.environ.get("CF_AI_MODEL_EMBED", "@cf/baai/bge-base-en-v1.5")
INCIDENT_ISSUE_TYPE_ID = "10013"  # AO JSM Incident — use the ID, not the name.
POINT_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
HTTP_TIMEOUT_SECONDS = 60.0


def _site() -> str:
    return os.environ["ATLASSIAN_SITE"].rstrip("/")


def _auth() -> tuple[str, str]:
    return (os.environ["ATLASSIAN_EMAIL"], os.environ["ATLASSIAN_API_TOKEN"])


def _project() -> str:
    return os.environ.get("ATLASSIAN_JIRA_PROJECT_KEY", "AO")


def _xqdrant() -> str:
    return os.environ.get("XQDRANT_URL", "http://localhost:6333").rstrip("/")


def _collection() -> str:
    return os.environ.get("XQDRANT_INCIDENTS_COLLECTION", "incidents")


def _cf_account() -> str:
    # Prefer the Workers-AI account split (a teammate's fresh budget), like the services.
    return os.environ.get("CF_AI_ACCOUNT_ID") or os.environ["CLOUDFLARE_ACCOUNT_ID"]


def _cf_token() -> str:
    return os.environ.get("CF_AI_API_TOKEN") or os.environ["CLOUDFLARE_API_TOKEN"]


def _cf_embed_url() -> str:
    return f"https://api.cloudflare.com/client/v4/accounts/{_cf_account()}/ai/run/{EMBED_MODEL}"


def _adf(description: str) -> dict[str, object]:
    """Wrap plain text in a minimal Atlassian Document Format paragraph."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
    }


def read_csv(path: str) -> list[dict[str, str]]:
    """Read incidents from the CSV; require ``summary`` + ``description`` columns."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("CSV has no data rows.")
    missing = {"summary", "description"} - set(rows[0])
    if missing:
        raise SystemExit(f"CSV missing required column(s): {', '.join(sorted(missing))}")
    return rows


def create_issue(client: httpx.Client, summary: str, description: str) -> str:
    """Create one AO Jira Incident and return its key (no priority/labels — AO rejects them)."""
    response = client.post(
        f"{_site()}/rest/api/3/issue",
        auth=_auth(),
        json={
            "fields": {
                "project": {"key": _project()},
                "summary": summary,
                "description": _adf(description),
                "issuetype": {"id": INCIDENT_ISSUE_TYPE_ID},
            }
        },
    )
    response.raise_for_status()
    key: str = response.json()["key"]
    return key


def embed(client: httpx.Client, text: str) -> list[float]:
    """Embed one text with BGE via Workers AI (768-dim)."""
    response = client.post(
        _cf_embed_url(),
        headers={"Authorization": f"Bearer {_cf_token()}"},
        json={"text": [text[:2000]]},
    )
    response.raise_for_status()
    vector: list[float] = response.json()["result"]["data"][0]
    return vector


def upsert(client: httpx.Client, key: str, summary: str, text: str, vector: list[float]) -> None:
    """Upsert one incident vector into the xqdrant incidents collection."""
    point = {
        "id": str(uuid.uuid5(POINT_ID_NAMESPACE, key)),
        "vector": vector,
        "payload": {
            "source_id": key,
            "title": summary,
            "text": text,
            "category": "custom",
            "source_type": "incident",
        },
    }
    response = client.put(
        f"{_xqdrant()}/collections/{_collection()}/points",
        params={"wait": "true"},
        json={"points": [point]},
    )
    response.raise_for_status()


def main() -> int:
    """Seed every CSV row into Jira AO + xqdrant incidents."""
    parser = argparse.ArgumentParser(description="Seed custom incidents for a tailored demo.")
    parser.add_argument("--csv", required=True, help="Path to the incidents CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Parse + validate only; no writes.")
    args = parser.parse_args()

    rows = read_csv(args.csv)
    print(f"→ {len(rows)} incident(s) from {args.csv}")
    if args.dry_run:
        for row in rows:
            print(f"  [dry-run] {row['summary'][:70]}")
        return 0

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        for index, row in enumerate(rows, 1):
            summary = row["summary"].strip()
            description = row["description"].strip()
            text = f"{summary}\n\n{description}"
            key = create_issue(client, summary, description)
            upsert(client, key, summary, text, embed(client, text))
            print(f"  [{index:3d}/{len(rows)}] {key}  {summary[:60]}")
            time.sleep(0.4)  # stay within Atlassian + CF rate limits
    print(f"✓ Seeded {len(rows)} incidents into {_project()} + xqdrant '{_collection()}'.")
    print("  Run /analyze on any of the new keys to see a tailored RCA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
