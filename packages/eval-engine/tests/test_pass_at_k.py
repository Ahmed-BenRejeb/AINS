"""Tests for the pass^k reliability metric (all() not any())."""

from __future__ import annotations

from eval_engine.metrics.pass_at_k import consistency_rate, pass_at_k
from trace_core import PASS_AT_K_TRIALS


def test_all_pass_is_one() -> None:
    """All k trials passing gives 1.0."""
    assert pass_at_k([True] * PASS_AT_K_TRIALS) == 1.0


def test_any_fail_is_zero() -> None:
    """A single failing trial collapses pass^k to 0.0 (this is the point)."""
    results = [True] * (PASS_AT_K_TRIALS - 1) + [False]
    assert pass_at_k(results) == 0.0


def test_uses_all_not_any() -> None:
    """7 passes and 1 fail is 0.0 — any() would wrongly return 1.0."""
    assert pass_at_k([True, True, True, True, True, True, True, False]) == 0.0


def test_empty_is_zero() -> None:
    """No trials cannot be a pass."""
    assert pass_at_k([]) == 0.0


def test_only_first_k_count() -> None:
    """Trials beyond k do not rescue or break the metric."""
    results = [True] * PASS_AT_K_TRIALS + [False]
    assert pass_at_k(results) == 1.0


def test_consistency_rate_is_average() -> None:
    """consistency_rate is the soft passing fraction."""
    assert consistency_rate([True, True, False, False]) == 0.5
    assert consistency_rate([True, True, True, True]) == 1.0


def test_consistency_rate_empty_is_zero() -> None:
    """An empty list has a 0.0 consistency rate."""
    assert consistency_rate([]) == 0.0
