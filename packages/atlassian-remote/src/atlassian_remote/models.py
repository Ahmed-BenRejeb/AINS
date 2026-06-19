"""Local response models for the atlassian-remote backend.

These compose the cross-package schemas from ``trace_core`` into the shapes the
HTTP API returns. They are package-internal (not shared), so they live here
rather than in ``trace-core``. The structured payloads themselves —
:class:`~trace_core.RcaDraft`, :class:`~trace_core.SearchResult` — always come
from ``trace_core`` and are never redefined.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from trace_core import RcaDraft, SearchResult


class AnalyzeResult(BaseModel):
    """Result of ``POST /analyze``: an RCA draft plus its supporting evidence.

    ``flag_for_human`` is derived from the draft's confidence (see
    :func:`atlassian_remote.rca_generator.needs_human_review`); it is surfaced
    here rather than on :class:`~trace_core.RcaDraft`, whose schema stays a pure
    model contract.
    """

    rca_draft: RcaDraft = Field(description="The structured root-cause-analysis draft.")
    similar: list[SearchResult] = Field(
        description="Similar past incidents retrieved from xqdrant (above threshold)."
    )
    runbooks: list[SearchResult] = Field(
        description="Relevant runbooks retrieved from xqdrant (above threshold)."
    )
    flag_for_human: bool = Field(
        description="True when the draft's confidence is below CONFIDENCE_THRESHOLD."
    )
