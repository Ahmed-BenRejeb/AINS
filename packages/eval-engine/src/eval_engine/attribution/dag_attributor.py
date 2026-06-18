"""VeriLA-style per-component failure attribution.

A run is modelled as a small DAG of components — ``retrieval → planning →
execution`` — and each recorded step is mapped onto one of them. When a run
fails, :func:`attribute_failure` walks the steps in order and blames the first
one that shows a failure signal, returning *which step, which component, and how
confident* (docs/BATTLE_PLAN.md §5; VeriLA credit assignment).
"""

from __future__ import annotations

from typing import Any

from trace_core import FailureAttribution, TraceRecord

# Component pipeline, in dependency order.
RETRIEVAL = "retrieval"
PLANNING = "planning"
EXECUTION = "execution"

_RETRIEVAL_HINTS = ("search", "retrieve", "fetch", "vector", "lookup", "query")

# Confidence levels by how explicit the failure signal is.
_CONF_EXPLICIT_ERROR = 0.9
_CONF_EMPTY_RETRIEVAL = 0.7
_CONF_MISSING_OUTCOME = 0.7
_CONF_FALLBACK = 0.5


def classify_component(record: TraceRecord) -> str:
    """Map a step to its DAG component from its kind and tool name."""
    if record.kind == "tool_call":
        tool = (record.metadata.tool_name or "").lower()
        if any(hint in tool for hint in _RETRIEVAL_HINTS):
            return RETRIEVAL
        return EXECUTION
    # llm_call, decision, state_snapshot are all planning/reasoning.
    return PLANNING


def _failure_signal(record: TraceRecord) -> tuple[str, float] | None:
    """Return (description, confidence) if a step looks failed, else None."""
    output: dict[str, Any] = record.output
    component = classify_component(record)

    if output.get("error"):
        return f"{component} step errored: {output['error']}", _CONF_EXPLICIT_ERROR
    if output.get("success") is False:
        return f"{component} step reported success=false", _CONF_EXPLICIT_ERROR
    if component == RETRIEVAL:
        results = output.get("results")
        if isinstance(results, list) and len(results) == 0:
            return "retrieval returned no results", _CONF_EMPTY_RETRIEVAL
    if component == EXECUTION and record.kind == "tool_call":
        if not (output.get("key") or output.get("id") or output.get("success")):
            return "execution produced no verifiable outcome", _CONF_MISSING_OUTCOME
    return None


def attribute_failure(records: list[TraceRecord]) -> FailureAttribution:
    """Identify the step/component that caused a run to fail.

    Walks steps in ``sequence`` order and blames the first one with a failure
    signal. If no single step stands out, blames the last execution step (or the
    last step) with low confidence so a human still gets a starting point.

    Args:
        records: The run's ordered steps (assumed to be a failing run).

    Returns:
        A :class:`trace_core.FailureAttribution`.
    """
    ordered = sorted(records, key=lambda r: r.sequence)

    for record in ordered:
        signal = _failure_signal(record)
        if signal is not None:
            description, confidence = signal
            return FailureAttribution(
                step=record.sequence,
                component=classify_component(record),
                description=description,
                confidence=confidence,
            )

    # No explicit signal — fall back to the last step as the likely culprit.
    if ordered:
        last = ordered[-1]
        return FailureAttribution(
            step=last.sequence,
            component=classify_component(last),
            description="no explicit failure signal; blaming final step by default",
            confidence=_CONF_FALLBACK,
        )

    return FailureAttribution(
        step=0,
        component=PLANNING,
        description="empty trace; nothing to attribute",
        confidence=_CONF_FALLBACK,
    )
