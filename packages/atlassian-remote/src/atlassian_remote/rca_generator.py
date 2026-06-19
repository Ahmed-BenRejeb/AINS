"""Root-cause-analysis drafting via Cloudflare Workers AI (Llama 3.3 70B).

Given an incident's text plus the similar past incidents and relevant runbooks
retrieved from xqdrant, the model drafts a :class:`trace_core.RcaDraft` —
**always** a structured Pydantic object, never free text (root atlassian-remote
CLAUDE.md). The prompt pins the exact JSON contract; :func:`generate_rca` strips
any markdown fence and validates the response against the schema.

:func:`needs_human_review` applies the confidence gate: a draft whose
``confidence_score`` is below ``CONFIDENCE_THRESHOLD`` (0.70, from ``trace_core``)
is flagged for a human.
"""

from __future__ import annotations

from trace_core import CONFIDENCE_THRESHOLD, RcaDraft, SearchResult

from . import cf_ai_client

_MAX_EVIDENCE_CHARS = 500
"""Per-item cap on retrieved text in the prompt — bounds CF Workers AI neuron use
(free tier: 10k/day; root atlassian-remote CLAUDE.md gotcha)."""

RCA_SYSTEM_PROMPT = (
    "You are Sentinel, an incident root-cause-analysis assistant for an SRE team. "
    "You are given an incident and evidence retrieved from a knowledge base of past "
    "incidents and runbooks. Produce a single root-cause-analysis draft.\n\n"
    "Output ONLY a valid JSON object — no prose, no markdown fences — with exactly "
    "these keys:\n"
    '  "root_cause_hypothesis": string — the most likely root cause.\n'
    '  "evidence": array of strings — specific evidence (cite similar incident ids '
    "or runbook excerpts) supporting the hypothesis.\n"
    '  "severity_rationale": string — why the proposed severity was chosen.\n'
    '  "proposed_severity": one of "critical", "high", "medium", "low".\n'
    '  "proposed_assignee_team": string — the team to own this, inferred from '
    "similar past incidents.\n"
    '  "duplicate_check": array of strings — ids of similar incidents that look '
    "like semantic duplicates (empty array if none).\n"
    '  "knowledge_gaps": array of strings — topics with no matching runbook (empty '
    "array if every relevant area is covered).\n"
    '  "confidence_score": number between 0 and 1 — your confidence in this draft; '
    "use a low value when the evidence is thin or contradictory.\n"
)


def _truncate(text: str) -> str:
    """Trim retrieved text to the per-item evidence cap."""
    return text if len(text) <= _MAX_EVIDENCE_CHARS else text[:_MAX_EVIDENCE_CHARS] + "…"


def _format_hits(label: str, hits: list[SearchResult]) -> str:
    """Render retrieved hits as a numbered evidence block for the prompt."""
    if not hits:
        return f"{label}: (none retrieved above the relevance threshold)"
    lines = [f"{label}:"]
    for hit in hits:
        lines.append(f"- [{hit.id}] (score {hit.score:.2f}) {_truncate(hit.text)}")
    return "\n".join(lines)


def build_rca_prompt(
    incident_text: str,
    similar: list[SearchResult],
    runbooks: list[SearchResult],
) -> str:
    """Assemble the user prompt from the incident and its retrieved evidence.

    Args:
        incident_text: The incident summary + description text.
        similar: Similar past incidents from xqdrant.
        runbooks: Relevant runbooks from xqdrant.

    Returns:
        The user-role prompt string for the RCA model.
    """
    return (
        f"INCIDENT:\n{incident_text}\n\n"
        f"{_format_hits('SIMILAR PAST INCIDENTS', similar)}\n\n"
        f"{_format_hits('RELEVANT RUNBOOKS', runbooks)}\n\n"
        "Draft the root-cause analysis as the JSON object specified above."
    )


def _extract_json(raw: str) -> str:
    """Best-effort extraction of the JSON object from a model response.

    Strips an optional ```json``` fence, then narrows to the outermost ``{...}`` so
    a stray preamble does not break validation.

    Args:
        raw: The raw model response text.

    Returns:
        The JSON substring (validation happens in the caller).
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.startswith("json"):
            text = text[len("json") :]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def generate_rca(
    incident_text: str,
    similar: list[SearchResult],
    runbooks: list[SearchResult],
) -> RcaDraft:
    """Draft an :class:`trace_core.RcaDraft` for an incident via CF Workers AI.

    Args:
        incident_text: The incident summary + description text.
        similar: Similar past incidents retrieved from xqdrant.
        runbooks: Relevant runbooks retrieved from xqdrant.

    Returns:
        The validated structured RCA draft.

    Raises:
        pydantic.ValidationError: If the model output does not match the
            :class:`~trace_core.RcaDraft` schema.
    """
    messages = [
        {"role": "system", "content": RCA_SYSTEM_PROMPT},
        {"role": "user", "content": build_rca_prompt(incident_text, similar, runbooks)},
    ]
    raw = await cf_ai_client.cf_ai_chat(messages)
    return RcaDraft.model_validate_json(_extract_json(raw))


def needs_human_review(draft: RcaDraft) -> bool:
    """Whether a draft's confidence is below the human-review gate.

    Args:
        draft: The RCA draft to assess.

    Returns:
        ``True`` when ``confidence_score < CONFIDENCE_THRESHOLD`` (0.70).
    """
    return draft.confidence_score < CONFIDENCE_THRESHOLD
