"""Environment-driven configuration and named constants for the eval engine.

Centralises every env-var name, model id, threshold, and Atlassian field the
evaluator depends on, so no grader hardcodes them. Each constant carries the
origin (paper / spec / business rule) per the root ``CLAUDE.md`` coding standard.
"""

from __future__ import annotations

import os

# ─── Cloudflare Workers AI ─────────────────────────────────────────────────────


def cf_account_id() -> str:
    """Cloudflare account id for Workers AI calls.

    Prefers ``CF_AI_ACCOUNT_ID`` so Workers AI can run on a *separate* account
    (e.g. a teammate's) with its own free 10k-neuron/day budget, and falls back to
    ``CLOUDFLARE_ACCOUNT_ID``. D1 reads ``CLOUDFLARE_*`` directly, so the trace
    store stays on the primary account regardless.
    """
    return os.environ.get("CF_AI_ACCOUNT_ID") or os.environ["CLOUDFLARE_ACCOUNT_ID"]


def cf_api_token() -> str:
    """Cloudflare API token (Bearer) for Workers AI calls.

    Prefers ``CF_AI_API_TOKEN`` (pair it with ``CF_AI_ACCOUNT_ID``), falls back to
    ``CLOUDFLARE_API_TOKEN``.
    """
    return os.environ.get("CF_AI_API_TOKEN") or os.environ["CLOUDFLARE_API_TOKEN"]


def cf_ai_url() -> str:
    """Base URL for Workers AI ``run`` calls (account-scoped)."""
    return f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id()}/ai/run"


# Default model ids match root CLAUDE.md Section 0 / .env; env overrides win.
# Gemma 4 26B (a4b) replaces Llama 3.3 70B as the judge/RCA model — ~7x cheaper
# per output neuron (27,273 vs 204,805 neurons/M out), which matters because the
# calibrated judge runs twice per trial × PASS_AT_K_TRIALS.
_DEFAULT_MODEL_MAIN = "@cf/google/gemma-4-26b-a4b-it"
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

# ─── Drift detection (UC1 §2.3) ────────────────────────────────────────────────

DRIFT_PASS_RATE_DELTA_THRESHOLD = 0.2
"""Absolute pass-rate change between baseline and current that counts as drift.

Origin: UC1 acceptance criterion "detect meaningful shifts ... across runs over
time" (official brief §2.3). A 20-percentage-point swing in pass rate is a clear
behavioural regression/improvement worth surfacing, not trial-to-trial noise.
"""

DRIFT_DIMENSION_DELTA_THRESHOLD = 0.15
"""Absolute mean change in any single rubric dimension that counts as drift.

Origin: UC1 §2.3 + the judge rubric (``JUDGE_DIMENSIONS``). Catches a quality shift
isolated to one dimension (e.g. reasoning_quality) even when the overall pass/fail
outcome has not moved — brief Scenario B.
"""

DRIFT_SEMANTIC_DISTANCE_THRESHOLD = 0.15
"""Output-embedding centroid cosine distance that counts as semantic drift.

Origin: UC1 §2.3 "output characteristics". BGE (768-dim) embeddings of the agents'
output text are averaged per window; a centroid cosine distance at/above this means
the *shape* of outputs changed (length, structure, topic) even with no score change.
"""

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
