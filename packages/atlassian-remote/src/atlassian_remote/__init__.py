"""Sentinel atlassian-remote (UC3 heavy-compute backend).

The Forge Remote backend that runs the work the Forge sandbox cannot: text
embedding and xqdrant similarity search (:mod:`vector_search`), CF Workers AI RCA
drafting into a :class:`trace_core.RcaDraft` (:mod:`rca_generator`), and the
Atlassian REST calls that need exponential backoff (:mod:`atlassian_client`).
:func:`analyze_incident` orchestrates the full ``POST /analyze`` flow.

All LLM calls go through Cloudflare Workers AI (:mod:`cf_ai_client`); every shared
schema comes from ``trace_core`` and is never redefined here.
"""

from __future__ import annotations

from .analyzer import analyze_incident, resolve_incident_duplicate
from .cf_ai_client import cf_ai_chat, cf_ai_embed
from .duplicate_resolver import resolve_duplicate
from .models import AnalyzeResult, DuplicateResult
from .rca_generator import generate_rca, needs_human_review
from .vector_search import search_similar

__all__ = [
    "AnalyzeResult",
    "DuplicateResult",
    "analyze_incident",
    "cf_ai_chat",
    "cf_ai_embed",
    "generate_rca",
    "needs_human_review",
    "resolve_duplicate",
    "resolve_incident_duplicate",
    "search_similar",
]
