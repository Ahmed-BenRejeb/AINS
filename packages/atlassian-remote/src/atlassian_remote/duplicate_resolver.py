"""Semantic duplicate detection via Cloudflare Workers AI (Llama 3.3 70B).

Given an incoming incident's text plus the most similar past incidents retrieved
from xqdrant, the model judges whether the incident is a **true semantic
duplicate** of one of them — the same underlying problem even when the wording,
service names, or symptoms differ. The output is **always** a structured
:class:`trace_core.DuplicateVerdict`, never free text (root atlassian-remote
CLAUDE.md). The prompt pins the exact JSON contract; :func:`resolve_duplicate`
strips any markdown fence and validates the response against the schema.

The prompt-rendering helpers (:func:`_extract_json`, :func:`_format_hits`) are
imported from :mod:`rca_generator` rather than re-implemented — they are already
the package's canonical CF-Workers-AI JSON helpers, and sharing them keeps the two
resolvers from drifting apart.

:func:`needs_human_review` is the graceful-degradation gate: auto-linking is only
safe when the model is confident *and* names a concrete duplicate, so it is
stricter than the RCA confidence gate.
"""

from __future__ import annotations

from trace_core import DUPLICATE_CONFIDENCE_THRESHOLD, DuplicateVerdict, SearchResult

from . import cf_ai_client
from .rca_generator import _extract_json, _format_hits

DUPLICATE_SYSTEM_PROMPT = (
    "You are Sentinel, a duplicate-incident detector for an SRE team. "
    "You are given a NEW incident and the most similar PAST incidents retrieved "
    "from a vector store. Decide whether the new incident is a TRUE SEMANTIC "
    "duplicate of one past incident — the same underlying problem, even if the "
    "wording, service names, or symptoms differ. Surface-level keyword overlap is "
    "NOT enough; different root causes are NOT duplicates.\n\n"
    "Output ONLY a valid JSON object — no prose, no markdown fences — with exactly "
    "these keys:\n"
    '  "is_duplicate": boolean — true only if it is genuinely the same incident.\n'
    '  "duplicate_of": string or null — the id of the matched past incident '
    "(null when is_duplicate is false).\n"
    '  "confidence": number between 0 and 1 — your confidence; use a low value '
    "when the match is ambiguous or the evidence is thin.\n"
    '  "rationale": string — concise semantic reasoning for the decision.\n'
    '  "explanation": string — a short, polite message addressed to the incident '
    "reporter, explaining that this looks like a duplicate and pointing to the "
    "matched incident.\n"
    '  "candidates": array of strings — ids of other plausible matches worth a '
    "human's attention (empty array if none).\n"
)


def build_duplicate_prompt(incident_text: str, similar: list[SearchResult]) -> str:
    """Assemble the user prompt from the new incident and its retrieved matches.

    Args:
        incident_text: The new incident's summary + description text.
        similar: Similar past incidents retrieved from xqdrant.

    Returns:
        The user-role prompt string for the duplicate-detection model.
    """
    return (
        f"NEW INCIDENT:\n{incident_text}\n\n"
        f"{_format_hits('SIMILAR PAST INCIDENTS', similar)}\n\n"
        "Judge whether the new incident is a semantic duplicate as the JSON object "
        "specified above."
    )


async def resolve_duplicate(
    incident_text: str,
    similar: list[SearchResult],
) -> DuplicateVerdict:
    """Judge whether an incident is a semantic duplicate via CF Workers AI.

    Args:
        incident_text: The new incident's summary + description text.
        similar: Similar past incidents retrieved from xqdrant.

    Returns:
        The validated structured duplicate verdict.

    Raises:
        pydantic.ValidationError: If the model output does not match the
            :class:`~trace_core.DuplicateVerdict` schema.
    """
    messages = [
        {"role": "system", "content": DUPLICATE_SYSTEM_PROMPT},
        {"role": "user", "content": build_duplicate_prompt(incident_text, similar)},
    ]
    raw = await cf_ai_client.cf_ai_chat(messages)
    return DuplicateVerdict.model_validate_json(_extract_json(raw))


def needs_human_review(verdict: DuplicateVerdict) -> bool:
    """Whether a verdict is too uncertain to auto-link (graceful-degradation gate).

    Auto-mutating Jira is only safe when the model is confident *and* names a
    concrete duplicate. This is stricter than the RCA gate: it also trips when the
    verdict is "not a duplicate" or has no ``duplicate_of`` target, so the Forge
    action never tries to link to a null issue.

    Args:
        verdict: The duplicate verdict to assess.

    Returns:
        ``True`` when the incident is not a duplicate, has no target, or the
        confidence is below ``DUPLICATE_CONFIDENCE_THRESHOLD`` (0.85).
    """
    return (
        not verdict.is_duplicate
        or verdict.duplicate_of is None
        or verdict.confidence < DUPLICATE_CONFIDENCE_THRESHOLD
    )
