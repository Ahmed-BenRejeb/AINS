"""Minimal Atlassian Jira client for filing eval-failure issues.

Creates an Incident in the AO JSM project when a verdict fails or is flagged for
human review. Follows the project's hard rules (root CLAUDE.md Section 10):

* use the issue-type **ID** ``10013`` — the name '[System] Incident' is rejected;
* do **not** send ``priority`` or ``labels`` — the AO project rejects them.

There is no Atlassian SDK here — it is a single authenticated REST call.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import (
    INCIDENT_ISSUE_TYPE_ID,
    atlassian_api_token,
    atlassian_email,
    atlassian_is_configured,
    atlassian_site,
    jira_project_key,
)

_ISSUE_TIMEOUT_SECONDS = 30.0


def _adf(text: str) -> dict[str, Any]:
    """Wrap plain text in a minimal Atlassian Document Format paragraph."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]},
        ],
    }


def build_issue_payload(summary: str, description: str) -> dict[str, Any]:
    """Build the Jira create-issue body for an eval failure.

    Deliberately omits ``priority`` and ``labels`` and uses the issue-type ID.

    Args:
        summary: Issue summary line.
        description: Plain-text description (wrapped as ADF).

    Returns:
        The ``{"fields": {...}}` request body.
    """
    return {
        "fields": {
            "project": {"key": jira_project_key()},
            "summary": summary,
            "issuetype": {"id": INCIDENT_ISSUE_TYPE_ID},
            "description": _adf(description),
        }
    }


async def create_eval_issue(summary: str, description: str) -> str | None:
    """Create a Jira Incident for a failed/flagged verdict.

    No-ops (returns ``None``) when Atlassian credentials are not configured, so
    evaluation never crashes in environments without Jira access.

    Args:
        summary: Issue summary line.
        description: Plain-text description.

    Returns:
        The created issue key (e.g. ``"AO-123"``), or ``None`` if not filed.
    """
    if not atlassian_is_configured():
        return None
    payload = build_issue_payload(summary, description)
    async with httpx.AsyncClient(timeout=_ISSUE_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{atlassian_site().rstrip('/')}/rest/api/3/issue",
            auth=(atlassian_email(), atlassian_api_token()),
            json=payload,
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    key = body.get("key")
    return str(key) if key is not None else None
