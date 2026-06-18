"""Tests for the deterministic code grader."""

from __future__ import annotations

from eval_engine.graders import code_grader
from trace_core import TraceRecord


def test_known_good_trace_passes(trace_pass: list[TraceRecord]) -> None:
    """A clean run passes every check with a perfect score."""
    result = code_grader.grade(trace_pass)
    assert result.passed is True
    assert result.failures == []
    assert result.score == 1.0


def test_known_bad_trace_fails(trace_fail_step2: list[TraceRecord]) -> None:
    """A run with a failed retrieval step fails the grader."""
    result = code_grader.grade(trace_fail_step2)
    assert result.passed is False
    assert result.failures
    assert result.score < 1.0


def test_bad_trace_flags_error_and_missing_outcome(
    trace_fail_step2: list[TraceRecord],
) -> None:
    """The failures call out both the tool error and the missing issue outcome."""
    result = code_grader.grade(trace_fail_step2)
    joined = " ".join(result.failures)
    assert "returned an error" in joined
    assert "did not create an issue" in joined


def test_loop_detection_flags_repeated_steps(trace_pass: list[TraceRecord]) -> None:
    """Three identical consecutive steps are detected as a loop."""
    looping = trace_pass[:1] * 3
    # Re-sequence so they are consecutive but distinctly ordered.
    looping = [s.model_copy(update={"sequence": i}) for i, s in enumerate(looping)]
    result = code_grader.grade(looping)
    assert any("loop detected" in f for f in result.failures)
