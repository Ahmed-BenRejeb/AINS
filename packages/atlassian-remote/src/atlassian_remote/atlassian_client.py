"""Atlassian REST client with exponential backoff on rate limits.

A thin async wrapper over the Jira/Confluence Cloud REST APIs — no Atlassian SDK,
just authenticated ``httpx`` calls. Auth is HTTP Basic over
``base64(ATLASSIAN_EMAIL:ATLASSIAN_API_TOKEN)`` (``httpx`` builds the header from
the ``auth`` tuple).

Every request goes through :meth:`AtlassianClient._request`, which retries on
HTTP 429 with exponential backoff (root ``CLAUDE.md`` §10 — Atlassian enforces a
points-based rate limit; always back off). The sleep is isolated in
:func:`_backoff_sleep` so tests can patch it to run instantly.

Hard rules for the AO project (root ``CLAUDE.md`` §10), enforced by
:func:`build_incident_fields`:

* use the issue-type **ID** ``10013`` — the name '[System] Incident' is rejected;
* do **not** send ``priority`` or ``labels``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .config import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_RETRIES,
    BACKOFF_MAX_SECONDS,
    INCIDENT_ISSUE_TYPE_ID,
    atlassian_api_token,
    atlassian_email,
    atlassian_site,
    jira_project_key,
)

_RATE_LIMITED = 429
_DEFAULT_TIMEOUT_SECONDS = 30.0


async def _backoff_sleep(seconds: float) -> None:
    """Sleep ``seconds`` between retries.

    Wrapped in a module-level function so tests can monkeypatch it to a no-op and
    exercise the retry loop without real delays.
    """
    await asyncio.sleep(seconds)


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Delay before the next retry: honour ``Retry-After``, else exponential.

    Args:
        response: The 429 response (may carry a ``Retry-After`` header).
        attempt: 0-based retry attempt index.

    Returns:
        Seconds to wait, capped at ``BACKOFF_MAX_SECONDS``.
    """
    header = response.headers.get("Retry-After")
    if header is not None:
        try:
            return min(float(header), BACKOFF_MAX_SECONDS)
        except ValueError:
            pass  # Non-numeric (HTTP-date) Retry-After → fall back to exponential.
    # 2.0 (not 2) keeps the exponent float-typed: int ** int is Any in typeshed.
    return min(BACKOFF_BASE_SECONDS * (2.0**attempt), BACKOFF_MAX_SECONDS)


def adf(text: str) -> dict[str, Any]:
    """Wrap plain text in a minimal Atlassian Document Format paragraph.

    Args:
        text: Plain text to wrap.

    Returns:
        An ADF ``doc`` node suitable for a Jira comment/description body.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]},
        ],
    }


def build_incident_fields(summary: str, description: dict[str, Any] | str) -> dict[str, Any]:
    """Build Jira ``fields`` for an AO Incident, obeying the project's hard rules.

    Uses the issue-type **ID** ``10013`` and deliberately omits ``priority`` and
    ``labels`` (the AO project rejects both). Pass an ADF doc for ``description``
    (or plain text, which is wrapped via :func:`adf`).

    Args:
        summary: Issue summary line.
        description: ADF doc node, or plain text to wrap as ADF.

    Returns:
        A ``fields`` dict ready for :meth:`AtlassianClient.create_issue`.
    """
    return {
        "project": {"key": jira_project_key()},
        "summary": summary,
        "issuetype": {"id": INCIDENT_ISSUE_TYPE_ID},
        "description": adf(description) if isinstance(description, str) else description,
    }


class AtlassianClient:
    """Authenticated async client for Jira + Confluence Cloud REST APIs.

    Credentials default to the environment (``ATLASSIAN_SITE`` /
    ``ATLASSIAN_EMAIL`` / ``ATLASSIAN_API_TOKEN``) but can be injected for tests.
    """

    def __init__(
        self,
        site: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        *,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Build a client.

        Args:
            site: Site base URL; defaults to ``ATLASSIAN_SITE``.
            email: Basic-auth user; defaults to ``ATLASSIAN_EMAIL``.
            api_token: Basic-auth token; defaults to ``ATLASSIAN_API_TOKEN``.
            timeout: Per-request timeout in seconds.
        """
        self._site = (site or atlassian_site()).rstrip("/")
        self._auth = (email or atlassian_email(), api_token or atlassian_api_token())
        self._timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one authenticated request, retrying on 429 with exponential backoff.

        Args:
            method: HTTP method (``GET``, ``POST``, ...).
            path: Path under the site root (e.g. ``/rest/api/3/issue/AO-1``).
            json: Optional JSON body.
            params: Optional query parameters.

        Returns:
            The parsed JSON response body (``{}`` if the response has no body).

        Raises:
            httpx.HTTPStatusError: On a non-2xx response other than retried 429s
                (and on a 429 that is still rate-limited after the final retry).
        """
        url = f"{self._site}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(method, url, auth=self._auth, json=json, params=params)
            for attempt in range(BACKOFF_MAX_RETRIES):
                if response.status_code != _RATE_LIMITED:
                    break
                await _backoff_sleep(_retry_after_seconds(response, attempt))
                response = await client.request(
                    method, url, auth=self._auth, json=json, params=params
                )
            response.raise_for_status()
            if not response.content:
                return {}
            body: dict[str, Any] = response.json()
            return body

    async def get_issue(self, key: str) -> dict[str, Any]:
        """Fetch a Jira issue by key (e.g. ``AO-123``).

        Args:
            key: The issue key.

        Returns:
            The issue resource (``key``, ``fields``, ...).
        """
        return await self._request("GET", f"/rest/api/3/issue/{key}")

    async def create_issue(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Create a Jira issue from a ``fields`` mapping.

        For AO incidents, build ``fields`` with :func:`build_incident_fields` so
        the issue-type ID and no-priority/no-labels rules are respected.

        Args:
            fields: The Jira ``fields`` object.

        Returns:
            The create response (``id``, ``key``, ``self``).
        """
        return await self._request("POST", "/rest/api/3/issue", json={"fields": fields})

    async def add_comment(self, key: str, body: dict[str, Any]) -> dict[str, Any]:
        """Add a comment to a Jira issue.

        Args:
            key: The issue key to comment on.
            body: The comment body in ADF (see :func:`adf`).

        Returns:
            The created comment resource.
        """
        return await self._request("POST", f"/rest/api/3/issue/{key}/comment", json={"body": body})

    async def create_confluence_page(self, space: str, title: str, body: str) -> dict[str, Any]:
        """Create a Confluence page in ``space`` with ``storage``-format body.

        Args:
            space: The Confluence space key (e.g. ``SENT``).
            title: The page title (must be unique within the space).
            body: Page content in Confluence ``storage`` (XHTML) format.

        Returns:
            The created page resource.
        """
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        return await self._request("POST", "/wiki/rest/api/content", json=payload)

    async def search_jql(self, jql: str) -> dict[str, Any]:
        """Run a JQL search and return the matching issues.

        Args:
            jql: A JQL query string.

        Returns:
            The search response (``issues``, paging metadata).
        """
        return await self._request("POST", "/rest/api/3/search/jql", json={"jql": jql})
