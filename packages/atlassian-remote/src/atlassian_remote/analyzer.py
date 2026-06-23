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

from . import duplicate_resolver, eval_client, rca_generator, recording, vector_search
from .atlassian_client import AtlassianClient
from .config import incidents_collection, replay_link, runbooks_collection
from .dimension_label_map import unmapped_dimensions
from .models import AnalyzeResult, DuplicateResult


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


def _attribution_summary(hits: list[Any], *, limit: int = 3) -> list[dict[str, object]]:
    """Summarise top hits' XQdrant dimension attributions for trace metadata."""
    summary: list[dict[str, object]] = []
    for hit in hits[:limit]:
        dims = dict(hit.attribution.dims)
        terms = dict(hit.attribution.terms)
        unmapped = unmapped_dimensions(dims)
        summary.append(
            {
                "id": hit.id,
                "score": hit.score,
                "dims": dims,
                "terms": terms,
                "unmapped_dims": unmapped,
                "confidence_margin": hit.attribution.confidence_margin,
            }
        )
    return summary


def _attribution_preview(hits: list[Any]) -> str:
    """One-line explainability preview for the trace output column."""
    if not hits:
        return ""
    attr = hits[0].attribution
    if attr.terms:
        return ", ".join(f"{label}={v:.2f}" for label, v in list(attr.terms.items())[:3])
    if attr.dims:
        return ", ".join(f"d{d}={v:.2f}" for d, v in list(attr.dims.items())[:3])
    return ""


def _record_search(
    recorder: recording.RunRecorder,
    label: str,
    collection: str,
    incident_text: str,
    k: int,
    hits: list[Any],
) -> None:
    """Tape one xqdrant retrieval as a tool_call step on the run's trace."""
    top = f", top {hits[0].score:.3f}" if hits else ""
    margin = hits[0].attribution.confidence_margin if hits else None
    margin_note = f" · margin {margin:.2f}" if margin is not None else ""
    preview = _attribution_preview(hits)
    dims_note = f" · {preview}" if preview else ""
    recorder.record_tool_call(
        tool_name="xqdrant.query_points",
        arguments={"collection": collection, "k": k},
        output={
            "count": len(hits),
            "top_score": hits[0].score if hits else None,
            "hits": [hit.id for hit in hits],
            "attributions": _attribution_summary(hits),
        },
        input_preview=f"search {label} (k={k}) for: {incident_text[:140]}",
        output_preview=f"{len(hits)} {label} hit(s){top}{margin_note}{dims_note}",
        extra_metadata={"attributions": _attribution_summary(hits)} if hits else None,
    )


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
        # Embed the incident once and reuse the vector for both collections, then
        # tape each retrieval as a tool_call so the trace reads
        # embed -> search incidents -> search runbooks -> reason.
        embedding = await vector_search.cf_ai_embed_query(incident_text)
        similar = await vector_search.search_similar(
            incident_text, incidents_collection(), k=k, embedding=embedding
        )
        _record_search(recorder, "incidents", incidents_collection(), incident_text, k, similar)
        runbooks = await vector_search.search_similar(
            incident_text, runbooks_collection(), k=k, embedding=embedding
        )
        _record_search(recorder, "runbooks", runbooks_collection(), incident_text, k, runbooks)
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


async def resolve_incident_duplicate(
    incident_key: str,
    requested_by: str,
    *,
    k: int = MAX_RETRIEVAL_RESULTS,
) -> DuplicateResult:
    """Run the semantic-duplicate-resolution pipeline for one Jira incident.

    Fetches the incident, flattens it to text, retrieves the most similar past
    incidents from xqdrant (incidents only — duplicates are incident-to-incident),
    judges whether it is a semantic duplicate (:mod:`duplicate_resolver`), and
    gates the verdict for human review.

    Args:
        incident_key: The Jira issue key to check (e.g. ``AO-123``).
        requested_by: Atlassian account id of the requester (for audit context).
        k: Top-k cap for the xqdrant retrieval.

    Returns:
        A :class:`DuplicateResult` with the verdict, supporting hits, and the
        human-review flag.
    """
    del requested_by  # Carried for audit context; not used in the computation.
    issue = await AtlassianClient().get_issue(incident_key)
    incident_text = extract_incident_text(issue)

    similar = await vector_search.search_similar(incident_text, incidents_collection(), k=k)

    verdict = await duplicate_resolver.resolve_duplicate(incident_text, similar)
    return DuplicateResult(
        verdict=verdict,
        similar=similar,
        flag_for_human=duplicate_resolver.needs_human_review(verdict),
    )
