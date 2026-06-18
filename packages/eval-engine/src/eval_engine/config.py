"""Environment-driven configuration and named constants for the eval engine.

Centralises every env-var name, model id, threshold, and Atlassian field the
evaluator depends on, so no grader hardcodes them. Each constant carries the
origin (paper / spec / business rule) per the root ``CLAUDE.md`` coding standard.
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
_DEFAULT_MODEL_SAFETY = "@cf/meta/llama-guard-3-8b"
_DEFAULT_MODEL_EMBED = "@cf/baai/bge-base-en-v1.5"


def model_main() -> str:
    """Main judge/RCA model (``CF_AI_MODEL_MAIN``)."""
    return os.environ.get("CF_AI_MODEL_MAIN", _DEFAULT_MODEL_MAIN)


def model_safety() -> str:
    """Llama Guard safety model (``CF_AI_MODEL_SAFETY``)."""
    return os.environ.get("CF_AI_MODEL_SAFETY", _DEFAULT_MODEL_SAFETY)


def model_embed() -> str:
    """BGE embedding model (``CF_AI_MODEL_EMBED``)."""
    return os.environ.get("CF_AI_MODEL_EMBED", _DEFAULT_MODEL_EMBED)


CF_TIMEOUT_SECONDS = 30.0
"""Per-call timeout for Workers AI; Forge's own limit is 25s (atlassian-remote)."""

DEFAULT_MAX_TOKENS = 1000
"""Default completion budget for a judge call (root CLAUDE.md Section 7)."""

# ─── Judge scoring ─────────────────────────────────────────────────────────────

JUDGE_DIMENSIONS: tuple[str, ...] = ("correctness", "efficiency", "safety", "reasoning_quality")
"""Rubric dimensions the LLM judge scores (task UC1 spec)."""

JUDGE_PASS_THRESHOLD = 0.6
"""Mean dimension score at/above which the judge's verdict is ``pass``.

Origin: τ-bench-style rubric scoring — a run must clear a majority-quality bar
across dimensions to pass. Kept distinct from ``CONFIDENCE_THRESHOLD`` (0.70),
which gates *human review*, not pass/fail.
"""

# ─── Code grader ───────────────────────────────────────────────────────────────

TOKEN_BUDGET = 100_000
"""Soft cap on total LLM tokens across a run before the code grader flags waste.

Origin: efficiency guardrail (docs/BATTLE_PLAN.md §5 efficiency dimension). Only
enforced when steps report ``usage.total_tokens``; absent usage is not penalised.
"""

MAX_REPEATED_STEPS = 3
"""Number of identical consecutive steps that counts as a loop (loop detection)."""

# ─── Atlassian (verdict → Jira issue) ──────────────────────────────────────────

INCIDENT_ISSUE_TYPE_ID = "10013"
"""AO JSM Incident issue-type ID. Use the ID — the name '[System] Incident' is
rejected by the API (root CLAUDE.md Section 10)."""


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
    """Jira project key for filed eval issues (``ATLASSIAN_JIRA_PROJECT_KEY``, default AO)."""
    return os.environ.get("ATLASSIAN_JIRA_PROJECT_KEY", "AO")


def atlassian_is_configured() -> bool:
    """True only if all three Atlassian credentials are present in the env."""
    return all(
        os.environ.get(key) for key in ("ATLASSIAN_SITE", "ATLASSIAN_EMAIL", "ATLASSIAN_API_TOKEN")
    )


# ─── Replay deep links ─────────────────────────────────────────────────────────

_DEFAULT_FLIGHT_URL = "https://flight.ahmedxsaad.me"


def replay_link(run_id: str) -> str:
    """Deep link to the flight-recorder replay for a run (``FLIGHT_RECORDER_URL``)."""
    base = os.environ.get("FLIGHT_RECORDER_URL", _DEFAULT_FLIGHT_URL).rstrip("/")
    return f"{base}/runs/{run_id}"
