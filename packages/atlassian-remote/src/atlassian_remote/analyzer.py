"""Orchestration for ``POST /analyze`` — incident key in, recorded+judged RCA out.

Ties the whole system together (Phase 4 end-to-end loop):

1. Fetch the Jira incident via :class:`AtlassianClient` and flatten it to text.
2. Open a :class:`~atlassian_remote.recording.RunRecorder` so every CF Workers AI
   call below is taped into the run's cassette (flight recorder, UC2).
3. Retrieve similar incidents + relevant runbooks from xqdrant
   (:mod:`vector_search`) and draft an :class:`trace_core.RcaDraft`
   (:mod:`rca_generator`); gate it for human review.
4. Persist the run manifest, then ask the eval engine (UC1) to judge the run —
   the verdict (and any auto-filed Jira Incident) comes back on the response.

The collaborators are referenced as modules (``vector_search.search_similar``,
``recording.persist_manifest``, ``eval_client.request_evaluation``) so tests can
monkeypatch each step independently and never hit the network.
"""

from __future__ import annotations

from typing import Any

from trace_core import MAX_RETRIEVAL_RESULTS

from . import eval_client, rca_generator, recording, vector_search
from .atlassian_client import AtlassianClient
from .config import incidents_collection, replay_link, runbooks_collection
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
        An :class:`AnalyzeResult` with the RCA draft, supporting hits, the
        human-review flag, the eval engine's verdict, and the replay deep link.
    """
    del requested_by  # Carried for audit context; not used in the computation.
    run_id = recording.new_run_id()
    issue = await AtlassianClient().get_issue(incident_key)
    incident_text = extract_incident_text(issue)

    with recording.RunRecorder(run_id) as recorder:
        similar = await vector_search.search_similar(incident_text, incidents_collection(), k=k)
        runbooks = await vector_search.search_similar(incident_text, runbooks_collection(), k=k)
        draft = await rca_generator.generate_rca(incident_text, similar, runbooks)

    recording.persist_manifest(
        run_id,
        step_count=recorder.step_count,
        task_id=incident_key,
        started_at=recorder.started_at,
    )
    verdict = await eval_client.request_evaluation(run_id)

    return AnalyzeResult(
        run_id=run_id,
        rca_draft=draft,
        similar=similar,
        runbooks=runbooks,
        flag_for_human=rca_generator.needs_human_review(draft),
        eval_verdict=verdict,
        replay_link=replay_link(run_id),
    )
