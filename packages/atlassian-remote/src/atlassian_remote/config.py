"""Environment-driven configuration and named constants for atlassian-remote.

Centralises every env-var name, model id, threshold, and Atlassian field this
backend depends on, so no module hardcodes them (root ``CLAUDE.md`` §6). Mirrors
the ``eval-engine`` config module; thresholds that cross packages
(``VECTOR_SIMILARITY_THRESHOLD``, ``CONFIDENCE_THRESHOLD``) are imported from
``trace_core`` rather than re-read from the environment.
"""

from __future__ import annotations

import os

# ─── Cloudflare Workers AI ─────────────────────────────────────────────────────


def cf_account_id() -> str:
    """Cloudflare account id (``CLOUDFLARE_ACCOUNT_ID``)."""
    return os.environ["CLOUDFLARE_ACCOUNT_ID"]


def cf_api_token() -> str:
    """Cloudflare API token used as Bearer auth (``CLOUDFLARE_API_TOKEN``)."""
    return os.environ["CLOUDFLARE_API_TOKEN"]


def cf_ai_url() -> str:
    """Base URL for Workers AI ``run`` calls (account-scoped)."""
    return f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id()}/ai/run"


# Default model ids match root CLAUDE.md Section 0 / .env; env overrides win.
_DEFAULT_MODEL_MAIN = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
_DEFAULT_MODEL_EMBED = "@cf/baai/bge-base-en-v1.5"


def model_main() -> str:
    """Main RCA model — Llama 3.3 70B (``CF_AI_MODEL_MAIN``)."""
    return os.environ.get("CF_AI_MODEL_MAIN", _DEFAULT_MODEL_MAIN)


def model_embed() -> str:
    """BGE embedding model, 768-dim (``CF_AI_MODEL_EMBED``)."""
    return os.environ.get("CF_AI_MODEL_EMBED", _DEFAULT_MODEL_EMBED)


CF_TIMEOUT_SECONDS = 30.0
"""Per-call timeout for Workers AI. Forge's own request limit is 25s, so the
orchestrated ``/analyze`` flow (embed + 2 searches + 1 chat) must stay well under
it (root atlassian-remote CLAUDE.md — keep remote calls under 15s)."""

DEFAULT_MAX_TOKENS = 1024
"""Completion budget for one RCA draft (root CLAUDE.md Section 7 baseline)."""

# ─── xqdrant (vector search — internal only) ───────────────────────────────────

_DEFAULT_XQDRANT_URL = "http://localhost:6333"
_DEFAULT_INCIDENTS_COLLECTION = "incidents"
_DEFAULT_RUNBOOKS_COLLECTION = "runbooks"


def xqdrant_url() -> str:
    """xqdrant base URL (``XQDRANT_URL``; localhost:6333, internal only)."""
    return os.environ.get("XQDRANT_URL", _DEFAULT_XQDRANT_URL)


def incidents_collection() -> str:
    """Collection name for seeded incidents (``XQDRANT_INCIDENTS_COLLECTION``)."""
    return os.environ.get("XQDRANT_INCIDENTS_COLLECTION", _DEFAULT_INCIDENTS_COLLECTION)


def runbooks_collection() -> str:
    """Collection name for seeded runbooks (``XQDRANT_RUNBOOKS_COLLECTION``)."""
    return os.environ.get("XQDRANT_RUNBOOKS_COLLECTION", _DEFAULT_RUNBOOKS_COLLECTION)


# ─── Atlassian REST ────────────────────────────────────────────────────────────

INCIDENT_ISSUE_TYPE_ID = "10013"
"""AO JSM Incident issue-type ID. Use the ID — the name '[System] Incident' is
rejected by the API (root CLAUDE.md Section 10). Creating issues in AO must also
omit ``priority`` and ``labels``."""


def atlassian_site() -> str:
    """Atlassian site base URL (``ATLASSIAN_SITE``)."""
    return os.environ["ATLASSIAN_SITE"]


def atlassian_email() -> str:
    """Atlassian account email for basic auth (``ATLASSIAN_EMAIL``)."""
    return os.environ["ATLASSIAN_EMAIL"]


def atlassian_api_token() -> str:
    """Atlassian API token for basic auth (``ATLASSIAN_API_TOKEN``)."""
    return os.environ["ATLASSIAN_API_TOKEN"]


def jira_project_key() -> str:
    """Jira project key for created issues (``ATLASSIAN_JIRA_PROJECT_KEY``, default AO)."""
    return os.environ.get("ATLASSIAN_JIRA_PROJECT_KEY", "AO")


def atlassian_is_configured() -> bool:
    """True only if all three Atlassian credentials are present in the env."""
    return all(
        os.environ.get(key) for key in ("ATLASSIAN_SITE", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN")
    )


# ─── Atlassian rate-limit backoff (429) ────────────────────────────────────────

BACKOFF_MAX_RETRIES = 5
"""Maximum retry attempts on HTTP 429 before giving up (root CLAUDE.md §10 —
Atlassian rate limits, always back off). 5 covers transient throttling without
holding a Forge request open past its 25s budget."""

BACKOFF_BASE_SECONDS = 0.5
"""Base delay for exponential backoff: ``BASE * 2**attempt`` (0.5, 1, 2, 4, ...)."""

BACKOFF_MAX_SECONDS = 8.0
"""Ceiling on a single backoff sleep so retries never blow the Forge timeout."""

# ─── Forge Remote auth ─────────────────────────────────────────────────────────


def forge_remote_secret() -> str:
    """Shared secret every Forge request must present (``FORGE_REMOTE_SECRET``)."""
    return os.environ["FORGE_REMOTE_SECRET"]
