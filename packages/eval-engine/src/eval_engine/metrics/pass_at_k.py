"""The ``pass^k`` reliability metric (τ-bench, k=8).

``pass^k`` requires **all** k independent trials to succeed — it exposes the
catastrophic inconsistency that ``pass@1`` hides (GPT-4o ~61% pass@1 collapses to
~25% pass^8). Use :func:`pass_at_k`, never ``any()``.
"""

from __future__ import annotations

from trace_core import PASS_AT_K_TRIALS


def pass_at_k(results: list[bool], k: int = PASS_AT_K_TRIALS) -> float:
    """Return 1.0 only if all of the first ``k`` trials passed, else 0.0.

    Args:
        results: Per-trial pass/fail booleans.
        k: Number of trials that must all pass (default :data:`PASS_AT_K_TRIALS`).

    Returns:
        ``1.0`` when there are results and every one of the first ``k`` is ``True``;
        ``0.0`` otherwise (including an empty list).
    """
    return float(bool(results) and all(results[:k]))


def consistency_rate(results: list[bool]) -> float:
    """Return the average passing rate across all trials (0.0 for an empty list).

    Unlike :func:`pass_at_k`, this is a soft signal — the fraction of trials that
    passed — useful for spotting flaky-but-not-broken runs.

    Args:
        results: Per-trial pass/fail booleans.

    Returns:
        ``sum(results) / len(results)``, or ``0.0`` when empty.
    """
    if not results:
        return 0.0
    return sum(results) / len(results)
