"""Render a run's trace into a flat transcript string for the LLM graders.

The judge and safety filter operate on text, not on ``TraceRecord`` objects, so
this turns an ordered run into a compact, deterministic transcript.
"""

from __future__ import annotations

import json

from trace_core import TraceRecord


def _compact(payload: dict[str, object]) -> str:
    """Compact, sorted-key JSON for one step's input/output."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_transcript(records: list[TraceRecord]) -> str:
    """Render an ordered run trace into a human/LLM-readable transcript.

    Args:
        records: The run's steps (any order; sorted by ``sequence`` here).

    Returns:
        One line per step: ``[seq] kind via model/tool: <input> -> <output>``.
    """
    lines: list[str] = []
    for record in sorted(records, key=lambda r: r.sequence):
        actor = record.metadata.model_id or record.metadata.tool_name or "-"
        lines.append(
            f"[{record.sequence}] {record.kind} via {actor}: "
            f"{_compact(record.input)} -> {_compact(record.output)}"
        )
    return "\n".join(lines)
