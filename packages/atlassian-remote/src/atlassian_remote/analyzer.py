"""Orchestration for ``POST /analyze`` — incident key in, RCA draft out.

Ties the package together: fetch the Jira incident via :class:`AtlassianClient`,
flatten its summary + ADF description to text, retrieve similar incidents and
relevant runbooks from xqdrant (:mod:`vector_search`), draft an
:class:`trace_core.RcaDraft` (:mod:`rca_generator`), and gate it for human review.

The collaborators are referenced as modules (``vector_search.search_similar``,
``rca_generator.generate_rca``) so tests can monkeypatch each step independently
and never hit the network.
"""

from __future__ import annotations

from typing import Any

from trace_core import MAX_RETRIEVAL_RESULTS

from . import rca_generator, vector_search
from .atlassian_client import AtlassianClient
from .config import incidents_collection, runbooks_collection
from .models import AnalyzeResult


def _adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format node (or any JSON) to plain text.

    Args:
        node: An ADF node, a list of nodes, or a leaf value.

    Returns:
        The concatenated text of every ``text`` leaf, depth-first.
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


def extract_incident_text(issue: dict[str, Any]) -> str:
    """Build the searchable/draftable text for an issue from its fields.

    Args:
        issue: A Jira issue resource (``fields.summary``, ``fields.description``).

    Returns:
        ``"<summary>\\n\\n<description>"`` with the ADF description flattened.
    """
    fields = issue.get("fields", {})
    summary = fields.get("summary") or ""
    description = fields.get("description")
    if isinstance(description, dict):
        description_text = _adf_to_text(description)
    else:
        description_text = description or ""
    return f"{summary}\n\n{description_text}".strip()


async def analyze_incident(
    incident_key: str,
    requested_by: str,
    *,
    k: int = MAX_RETRIEVAL_RESULTS,
) -> AnalyzeResult:
    """Run the full incident-analysis pipeline for one Jira incident.

    Args:
        incident_key: The Jira issue key to analyse (e.g. ``AO-123``).
        requested_by: Atlassian account id of the requester (for audit context).
        k: Top-k cap for each xqdrant retrieval.

    Returns:
        An :class:`AnalyzeResult` with the RCA draft, supporting hits, and the
        human-review flag.
    """
    del requested_by  # Carried for audit context; not used in the computation.
    issue = await AtlassianClient().get_issue(incident_key)
    incident_text = extract_incident_text(issue)

    similar = await vector_search.search_similar(incident_text, incidents_collection(), k=k)
    runbooks = await vector_search.search_similar(incident_text, runbooks_collection(), k=k)

    draft = await rca_generator.generate_rca(incident_text, similar, runbooks)
    return AnalyzeResult(
        rca_draft=draft,
        similar=similar,
        runbooks=runbooks,
        flag_for_human=rca_generator.needs_human_review(draft),
    )
