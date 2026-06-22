"""End-to-end reporter tests: one trace → one EvalVerdict (mocked CF AI)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from eval_engine import cf_ai_client
from eval_engine.config import JUDGE_DIMENSIONS
from eval_engine.models import SafetyResult
from eval_engine.verdicts import atlassian_client, reporter
from trace_core import TraceRecord


def _judge_json(score: float) -> str:
    dimensions = {
        dim: {"score": score, "reason": "r", "confidence": 0.9} for dim in JUDGE_DIMENSIONS
    }
    return json.dumps({"dimensions": dimensions, "confidence": 0.9, "self_critique": "ok"})


def _mock_cf(monkeypatch: pytest.MonkeyPatch, *, safe: bool, judge_score: float) -> None:
    async def fake_safety(text: str) -> SafetyResult:
        return SafetyResult(
            safe=safe, score=1.0 if safe else 0.0, categories=[] if safe else ["S1"]
        )

    async def fake_chat(messages: Any, model: Any = None, max_tokens: int = 1000) -> str:
        return _judge_json(judge_score)

    monkeypatch.setattr(cf_ai_client, "cf_ai_safety", fake_safety)
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", fake_chat)


async def test_passing_trace_yields_pass_verdict(
    monkeypatch: pytest.MonkeyPatch, trace_pass: list[TraceRecord]
) -> None:
    """A clean trace produces a pass verdict with no failure attribution."""
    _mock_cf(monkeypatch, safe=True, judge_score=0.9)

    verdict = await reporter.evaluate_run("run-pass-0001", 0, trace_pass, file_issue=False)

    assert verdict.verdict == "pass"
    assert verdict.failure_attribution is None
    assert verdict.self_evaluation is not None
    assert verdict.replay_link.endswith("/replay/run-pass-0001")


async def test_failing_trace_attributes_to_retrieval_step2(
    monkeypatch: pytest.MonkeyPatch, trace_fail_step2: list[TraceRecord]
) -> None:
    """A failed run is attributed to step 2 (retrieval) with self-evaluation set."""
    # Judge would pass, but the code grader fails on the retrieval error → fail.
    _mock_cf(monkeypatch, safe=True, judge_score=0.9)

    verdict = await reporter.evaluate_run("run-fail-0002", 0, trace_fail_step2, file_issue=False)

    assert verdict.verdict == "fail"
    assert verdict.failure_attribution is not None
    assert verdict.failure_attribution.step == 2
    assert verdict.failure_attribution.component == "retrieval"
    assert verdict.self_evaluation.self_critique


async def test_file_issue_failure_does_not_break_evaluation(
    monkeypatch: pytest.MonkeyPatch, trace_pass: list[TraceRecord]
) -> None:
    """A Jira filing error is swallowed — evaluate_run still returns the verdict."""
    _mock_cf(monkeypatch, safe=True, judge_score=0.3)  # low score → fail → triggers filing

    async def boom(summary: str, description: str) -> str | None:
        raise RuntimeError("jira 400 Bad Request")

    monkeypatch.setattr(atlassian_client, "create_eval_issue", boom)

    verdict = await reporter.evaluate_run("run-x", 0, trace_pass, file_issue=True)

    assert verdict.verdict == "fail"
    assert verdict.self_evaluation is not None


async def test_unsafe_trace_short_circuits_to_fail(
    monkeypatch: pytest.MonkeyPatch, trace_pass: list[TraceRecord]
) -> None:
    """An unsafe transcript fails immediately without an attribution-free pass."""
    chat_calls = [0]

    async def fake_safety(text: str) -> SafetyResult:
        return SafetyResult(safe=False, score=0.0, categories=["S1"])

    async def fake_chat(messages: Any, model: Any = None, max_tokens: int = 1000) -> str:
        chat_calls[0] += 1
        return _judge_json(0.9)

    monkeypatch.setattr(cf_ai_client, "cf_ai_safety", fake_safety)
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", fake_chat)

    verdict = await reporter.evaluate_run("run-pass-0001", 0, trace_pass, file_issue=False)

    assert verdict.verdict == "fail"
    assert "safety" in verdict.dimensions
    assert chat_calls[0] == 0  # judge was skipped
