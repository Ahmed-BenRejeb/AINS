"""Tests for the calibrated LLM judge (mocked CF Workers AI)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from eval_engine import cf_ai_client
from eval_engine.config import JUDGE_DIMENSIONS
from eval_engine.graders import llm_judge

ChatFn = Callable[..., Awaitable[str]]


def _verdict_json(score: float) -> str:
    """Build a judge JSON response with every dimension at ``score``."""
    dimensions = {
        dim: {"score": score, "reason": "because", "confidence": 0.9} for dim in JUDGE_DIMENSIONS
    }
    return json.dumps({"dimensions": dimensions, "confidence": 0.9, "self_critique": "ok"})


def _make_chat(responses: list[str]) -> tuple[ChatFn, list[int]]:
    """Return an async cf_ai_chat stub that yields queued responses, plus a counter."""
    queue = list(responses)
    calls = [0]

    async def fake_chat(messages: Any, model: Any = None, max_tokens: int = 1000) -> str:
        calls[0] += 1
        return queue.pop(0)

    return fake_chat, calls


async def test_position_bias_flip_marks_uncertain(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the two passes disagree, the verdict is uncertain and flagged."""
    chat, _ = _make_chat([_verdict_json(0.9), _verdict_json(0.2)])  # pass, then fail
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", chat)

    verdict = await llm_judge.calibrated_judge("transcript")

    assert verdict.verdict == "uncertain"
    assert verdict.flag_for_human is True
    assert verdict.reason == "position_bias_detected"


async def test_calibration_always_runs_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calibration is mandatory: the judge is always called exactly twice."""
    chat, calls = _make_chat([_verdict_json(0.9), _verdict_json(0.9)])
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", chat)

    await llm_judge.calibrated_judge("transcript")

    assert calls[0] == 2


async def test_stable_pass_is_not_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agreeing high scores yield a stable pass with no human flag."""
    chat, _ = _make_chat([_verdict_json(0.9), _verdict_json(0.9)])
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", chat)

    verdict = await llm_judge.calibrated_judge("transcript")

    assert verdict.verdict == "pass"
    assert verdict.flag_for_human is False
    assert verdict.reason is None


async def test_stable_fail_is_not_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agreeing low scores yield a stable fail (no bias, no flag)."""
    chat, _ = _make_chat([_verdict_json(0.2), _verdict_json(0.2)])
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", chat)

    verdict = await llm_judge.calibrated_judge("transcript")

    assert verdict.verdict == "fail"
    assert verdict.flag_for_human is False


async def test_single_judge_derives_verdict_from_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single (uncalibrated) judgment derives its verdict from the mean score."""
    chat, _ = _make_chat([_verdict_json(0.8)])
    monkeypatch.setattr(cf_ai_client, "cf_ai_chat", chat)

    verdict = await llm_judge.judge("transcript")

    assert verdict.verdict == "pass"
    assert set(verdict.dimensions) == set(JUDGE_DIMENSIONS)
