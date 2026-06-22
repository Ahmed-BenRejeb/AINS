"""Behavioural-drift detector (UC1 §2.3).

Compares a baseline window of :class:`trace_core.EvalVerdict` against a current
window and produces a :class:`trace_core.DriftReport`. Three signals are combined:

* **pass-rate drift** — change in the fraction of runs that passed.
* **dimension drift** — change in each rubric dimension's mean score (catches a
  quality shift even when the pass/fail outcome held).
* **semantic drift** — cosine distance between the baseline and current
  output-embedding centroids (catches output-shape shifts; brief Scenario B).

Drift is flagged when any signal crosses its threshold (config). The detector is
pure aside from the optional embedding call, which is routed through
:mod:`eval_engine.drift.embedder` (mockable), so it is fully unit-testable offline.
"""

from __future__ import annotations

from trace_core import DriftReport, EvalVerdict

from ..config import (
    DRIFT_DIMENSION_DELTA_THRESHOLD,
    DRIFT_PASS_RATE_DELTA_THRESHOLD,
    DRIFT_SEMANTIC_DISTANCE_THRESHOLD,
)
from ..langfuse_client import end_observation, start_span
from . import embedder


def _pass_rate(verdicts: list[EvalVerdict]) -> float:
    """Fraction of verdicts whose label is ``pass`` (0.0 for an empty window)."""
    if not verdicts:
        return 0.0
    return sum(v.verdict == "pass" for v in verdicts) / len(verdicts)


def _dimension_means(verdicts: list[EvalVerdict]) -> dict[str, float]:
    """Mean score per rubric dimension across a window of verdicts."""
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for verdict in verdicts:
        for name, dimension in verdict.dimensions.items():
            totals[name] = totals.get(name, 0.0) + dimension.score
            counts[name] = counts.get(name, 0) + 1
    return {name: totals[name] / counts[name] for name in totals}


def _overall_mean(dimension_means: dict[str, float]) -> float:
    """Mean across a window's per-dimension means (0.0 when there are none)."""
    if not dimension_means:
        return 0.0
    return sum(dimension_means.values()) / len(dimension_means)


def _build_summary(
    *,
    pass_rate_baseline: float,
    pass_rate_current: float,
    pass_rate_delta: float,
    most_shifted_dimension: str | None,
    dimension_deltas: dict[str, float],
    semantic_drift: float | None,
    drift_detected: bool,
) -> str:
    """Render a human-readable one-line summary from the computed drift fields."""
    parts = [
        f"pass rate {pass_rate_baseline:.0%} → {pass_rate_current:.0%} ({pass_rate_delta:+.0%})",
    ]
    if most_shifted_dimension is not None:
        delta = dimension_deltas[most_shifted_dimension]
        parts.append(f"largest dimension shift: {most_shifted_dimension} {delta:+.2f}")
    if semantic_drift is not None:
        parts.append(f"output semantic drift {semantic_drift:.2f}")
    headline = "Drift detected" if drift_detected else "No meaningful drift"
    return f"{headline}: " + "; ".join(parts) + "."


async def detect_drift(
    baseline: list[EvalVerdict],
    current: list[EvalVerdict],
    *,
    baseline_outputs: list[str] | None = None,
    current_outputs: list[str] | None = None,
) -> DriftReport:
    """Compare two windows of evaluation runs and report behavioural drift.

    Args:
        baseline: Verdicts from the reference window (e.g. last week's runs).
        current: Verdicts from the window under test (e.g. today's runs).
        baseline_outputs: Optional agent output texts for the baseline window; when
            both output lists are supplied, semantic drift is computed from them.
        current_outputs: Optional agent output texts for the current window.

    Returns:
        A :class:`trace_core.DriftReport` with the per-signal deltas, an overall
        ``drift_score``, the ``drift_detected`` flag, and a human-readable summary.
    """
    span = start_span(
        "drift-detection",
        input={"baseline_runs": len(baseline), "current_runs": len(current)},
    )

    pass_rate_baseline = _pass_rate(baseline)
    pass_rate_current = _pass_rate(current)
    pass_rate_delta = pass_rate_current - pass_rate_baseline

    baseline_means = _dimension_means(baseline)
    current_means = _dimension_means(current)
    dimension_deltas = {
        name: current_means.get(name, 0.0) - baseline_means.get(name, 0.0)
        for name in set(baseline_means) | set(current_means)
    }
    most_shifted_dimension = (
        max(dimension_deltas, key=lambda name: abs(dimension_deltas[name]))
        if dimension_deltas
        else None
    )
    max_dimension_delta = (
        max(abs(delta) for delta in dimension_deltas.values()) if dimension_deltas else 0.0
    )

    semantic_drift: float | None = None
    if baseline_outputs and current_outputs:
        baseline_centroid = await embedder.embed_centroid(baseline_outputs)
        current_centroid = await embedder.embed_centroid(current_outputs)
        if baseline_centroid is not None and current_centroid is not None:
            semantic_drift = embedder.cosine_distance(baseline_centroid, current_centroid)

    drift_detected = (
        abs(pass_rate_delta) >= DRIFT_PASS_RATE_DELTA_THRESHOLD
        or max_dimension_delta >= DRIFT_DIMENSION_DELTA_THRESHOLD
        or (semantic_drift is not None and semantic_drift >= DRIFT_SEMANTIC_DISTANCE_THRESHOLD)
    )
    drift_score = min(1.0, max(abs(pass_rate_delta), max_dimension_delta, semantic_drift or 0.0))

    report = DriftReport(
        baseline_run_count=len(baseline),
        current_run_count=len(current),
        pass_rate_baseline=pass_rate_baseline,
        pass_rate_current=pass_rate_current,
        pass_rate_delta=pass_rate_delta,
        mean_score_baseline=_overall_mean(baseline_means),
        mean_score_current=_overall_mean(current_means),
        dimension_deltas=dimension_deltas,
        most_shifted_dimension=most_shifted_dimension,
        semantic_drift=semantic_drift,
        drift_detected=drift_detected,
        drift_score=drift_score,
        summary=_build_summary(
            pass_rate_baseline=pass_rate_baseline,
            pass_rate_current=pass_rate_current,
            pass_rate_delta=pass_rate_delta,
            most_shifted_dimension=most_shifted_dimension,
            dimension_deltas=dimension_deltas,
            semantic_drift=semantic_drift,
            drift_detected=drift_detected,
        ),
    )

    end_observation(span, report.model_dump())
    return report
