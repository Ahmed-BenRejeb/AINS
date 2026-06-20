#!/usr/bin/env python3
"""seed_xqdrant.py — embed AO incidents + SENT runbooks into xqdrant.

Fetches every incident from the Jira ``AO`` project and every runbook page from the
Confluence ``SENT`` space, embeds each one with Cloudflare Workers AI BGE-Base-EN
(768-dim), and upserts the vectors into the local xqdrant ``incidents`` /
``runbooks`` collections. This is what makes UC3 retrieval real: until it runs the
collections are empty, so ``atlassian-remote`` ``/search`` and ``/analyze`` return
no evidence.

Idempotent: each point id is a deterministic UUID of the source id (Jira key /
Confluence page id), so re-running overwrites rather than duplicates.

Usage::

    make seed-xqdrant
    # or, with the environment loaded:
    set -a; source /srv/sentinel/.env; set +a
    uv run python scripts/seed_xqdrant.py

Requires in the environment: ``ATLASSIAN_SITE``, ``ATLASSIAN_EMAIL``,
``ATLASSIAN_API_TOKEN``, ``CLOUDFLARE_ACCOUNT_ID``, ``CLOUDFLARE_API_TOKEN`` (and
optionally ``XQDRANT_URL`` / ``CF_AI_MODEL_EMBED`` / the collection-name vars).
"""

from __future__ import annotations

import html
import os
import re
import sys
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

# ── Constants ─────────────────────────────────────────────────────────────────

EMBED_MODEL = os.environ.get("CF_AI_MODEL_EMBED", "@cf/baai/bge-base-en-v1.5")
"""BGE embedding model (768-dim) — matches the xqdrant collections + drift path."""

EMBED_BATCH_SIZE = 10
"""Texts per Workers AI embed call — batched to stay light on the free neuron tier."""

EMBED_MAX_CHARS = 2000
"""Per-document cap on embed input (~512 BGE tokens); full text is kept in payload."""

UPSERT_BATCH_SIZE = 100
"""Points per xqdrant upsert request."""

HTTP_TIMEOUT_SECONDS = 60.0

# Fixed namespace so a source id always maps to the same xqdrant point id (RFC 4122).
POINT_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

JIRA_PROJECT_KEY = os.environ.get("ATLASSIAN_JIRA_PROJECT_KEY", "AO")
CONFLUENCE_SPACE = "SENT"
INCIDENTS_COLLECTION = os.environ.get("XQDRANT_INCIDENTS_COLLECTION", "incidents")
RUNBOOKS_COLLECTION = os.environ.get("XQDRANT_RUNBOOKS_COLLECTION", "runbooks")

# Skip the eval-engine's own test Incidents so they never pollute the corpus.
_TEST_ISSUE_MARKER = "sentinel eval"


@dataclass
class SeedDoc:
    """One document to embed and store: a Jira incident or a Confluence runbook."""

    source_id: str  # Jira key (e.g. "AO-1") or Confluence page id
    title: str
    text: str  # full content, stored in the payload for attribution
    category: str
    source_type: str  # "incident" | "runbook"


# ── Config helpers ────────────────────────────────────────────────────────────


def _site() -> str:
    """Atlassian site base URL, trailing slash trimmed (``ATLASSIAN_SITE``)."""
    return os.environ["ATLASSIAN_SITE"].rstrip("/")


def _auth() -> tuple[str, str]:
    """HTTP Basic credentials (``ATLASSIAN_EMAIL`` / ``ATLASSIAN_API_TOKEN``)."""
    return (os.environ["ATLASSIAN_EMAIL"], os.environ["ATLASSIAN_API_TOKEN"])


def _xqdrant() -> str:
    """xqdrant base URL (``XQDRANT_URL``; localhost:6333, internal only)."""
    return os.environ.get("XQDRANT_URL", "http://localhost:6333").rstrip("/")


def _cf_embed_url() -> str:
    """Cloudflare Workers AI BGE run endpoint (account-scoped)."""
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    return f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{EMBED_MODEL}"


# ── Text extraction ───────────────────────────────────────────────────────────


def _adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format node (or any JSON) to plain text.

    Mirrors ``atlassian_remote.analyzer._adf_to_text`` — inlined to keep this
    seeding script standalone (no app-package import chain).
    """
    if isinstance(node, dict):
        parts: list[str] = []
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            parts.append(node["text"])
        for child in node.get("content", []) or []:
            parts.append(_adf_to_text(child))
        return " ".join(part for part in parts if part)
    if isinstance(node, list):
        return " ".join(_adf_to_text(item) for item in node)
    return ""


def _strip_html(raw: str) -> str:
    """Reduce Confluence storage-format XHTML to collapsed plain text."""
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def _point_id(source_id: str) -> str:
    """Deterministic xqdrant point id (UUIDv5) for a source id."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, source_id))


def _truncate(text: str) -> str:
    """Clamp embed input to ``EMBED_MAX_CHARS`` (payload keeps the full text)."""
    return text[:EMBED_MAX_CHARS]


# ── Fetch ─────────────────────────────────────────────────────────────────────


def fetch_incidents(client: httpx.Client) -> list[SeedDoc]:
    """Fetch every AO incident (summary + flattened description) via Jira search.

    Uses ``/rest/api/3/search/jql`` (the classic ``/search`` is deprecated on
    Cloud) with token pagination, and excludes the eval-engine's own test issues.

    Args:
        client: An open HTTP client.

    Returns:
        One :class:`SeedDoc` per incident, oldest first.
    """
    jql = f'project = {JIRA_PROJECT_KEY} AND summary !~ "Sentinel" ORDER BY created ASC'
    docs: list[SeedDoc] = []
    next_token: str | None = None
    while True:
        params: dict[str, Any] = {
            "jql": jql,
            "maxResults": 100,
            "fields": "summary,description,labels",
        }
        if next_token:
            params["nextPageToken"] = next_token
        response = client.get(f"{_site()}/rest/api/3/search/jql", params=params, auth=_auth())
        response.raise_for_status()
        body = response.json()
        issues = body.get("issues", [])
        for issue in issues:
            fields = issue.get("fields", {})
            summary = fields.get("summary") or ""
            if _TEST_ISSUE_MARKER in summary.lower():
                continue  # belt-and-suspenders: skip our own eval Incidents
            description = fields.get("description")
            description_text = (
                _adf_to_text(description) if isinstance(description, dict) else (description or "")
            )
            labels = fields.get("labels") or []
            docs.append(
                SeedDoc(
                    source_id=issue["key"],
                    title=summary,
                    text=f"{summary}\n\n{description_text}".strip(),
                    category=labels[0] if labels else "uncategorized",
                    source_type="incident",
                )
            )
        next_token = body.get("nextPageToken")
        if not next_token or not issues:
            return docs


def fetch_runbooks(client: httpx.Client) -> list[SeedDoc]:
    """Fetch every runbook page in the SENT Confluence space (title + body text).

    Args:
        client: An open HTTP client.

    Returns:
        One :class:`SeedDoc` per page.
    """
    listing = client.get(
        f"{_site()}/wiki/rest/api/content",
        params={"spaceKey": CONFLUENCE_SPACE, "type": "page", "limit": 50},
        auth=_auth(),
    )
    listing.raise_for_status()
    docs: list[SeedDoc] = []
    for page in listing.json().get("results", []):
        page_id = str(page["id"])
        title = page.get("title", "")
        detail = client.get(
            f"{_site()}/wiki/rest/api/content/{page_id}",
            params={"expand": "body.storage"},
            auth=_auth(),
        )
        detail.raise_for_status()
        storage = detail.json().get("body", {}).get("storage", {}).get("value", "")
        docs.append(
            SeedDoc(
                source_id=page_id,
                title=title,
                text=f"{title}\n\n{_strip_html(storage)}".strip(),
                category=CONFLUENCE_SPACE,
                source_type="runbook",
            )
        )
    return docs


# ── Embed + upsert ────────────────────────────────────────────────────────────


def embed_texts(client: httpx.Client, texts: list[str]) -> list[list[float]]:
    """Embed texts with BGE via Workers AI, in batches of ``EMBED_BATCH_SIZE``.

    Args:
        client: An open HTTP client.
        texts: The strings to embed.

    Returns:
        One 768-dim vector per input text, in order.
    """
    vectors: list[list[float]] = []
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = [_truncate(text) for text in texts[start : start + EMBED_BATCH_SIZE]]
        response = client.post(
            _cf_embed_url(),
            headers={"Authorization": f"Bearer {token}"},
            json={"text": batch},
        )
        response.raise_for_status()
        vectors.extend(response.json()["result"]["data"])
    return vectors


def upsert(
    client: httpx.Client, collection: str, docs: list[SeedDoc], vectors: list[list[float]]
) -> None:
    """Upsert ``docs`` (with their ``vectors``) into an xqdrant collection.

    Args:
        client: An open HTTP client.
        collection: Target collection name.
        docs: The documents (payload source).
        vectors: One embedding per doc, aligned by index.
    """
    points = [
        {
            "id": _point_id(doc.source_id),
            "vector": vector,
            "payload": {
                "source_id": doc.source_id,
                "title": doc.title,
                "text": doc.text,
                "category": doc.category,
                "source_type": doc.source_type,
            },
        }
        for doc, vector in zip(docs, vectors, strict=True)
    ]
    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        response = client.put(
            f"{_xqdrant()}/collections/{collection}/points",
            params={"wait": "true"},
            json={"points": points[start : start + UPSERT_BATCH_SIZE]},
        )
        response.raise_for_status()


def collection_count(client: httpx.Client, collection: str) -> int:
    """Return the current ``points_count`` of an xqdrant collection."""
    response = client.get(f"{_xqdrant()}/collections/{collection}")
    response.raise_for_status()
    return int(response.json()["result"].get("points_count") or 0)


def _seed(client: httpx.Client, collection: str, docs: list[SeedDoc], label: str) -> None:
    """Embed and upsert one corpus, printing progress."""
    if not docs:
        print(f"  ! no {label} found — nothing to seed")
        return
    print(f"  embedding {len(docs)} {label} ...")
    vectors = embed_texts(client, [doc.text for doc in docs])
    print(f"  upserting {len(vectors)} {label} into '{collection}' ...")
    upsert(client, collection, docs, vectors)


def main() -> int:
    """Seed both collections and print the resulting point counts."""
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        print(f"→ fetching incidents from Jira project {JIRA_PROJECT_KEY} ...")
        incidents = fetch_incidents(client)
        print(f"  {len(incidents)} incidents")
        print(f"→ fetching runbooks from Confluence space {CONFLUENCE_SPACE} ...")
        runbooks = fetch_runbooks(client)
        print(f"  {len(runbooks)} runbooks")

        _seed(client, INCIDENTS_COLLECTION, incidents, "incidents")
        _seed(client, RUNBOOKS_COLLECTION, runbooks, "runbooks")

        incident_points = collection_count(client, INCIDENTS_COLLECTION)
        runbook_points = collection_count(client, RUNBOOKS_COLLECTION)
    print(
        f"\n✓ xqdrant seeded — "
        f"{INCIDENTS_COLLECTION}: {incident_points} points | "
        f"{RUNBOOKS_COLLECTION}: {runbook_points} points"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
