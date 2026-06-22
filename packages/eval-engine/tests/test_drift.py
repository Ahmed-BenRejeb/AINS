"""Drift detector + embedder tests — CF Workers AI embedding is monkeypatched."""

from __future__ import annotations

from typing import Any

import pytest
from eval_engine import cf_ai_client
from eval_engine.drift import detector, embedder
from trace_core import DimensionScore, EvalVerdict, SelfEvaluation, VerdictLabel


def _verdict(verdict: VerdictLabel, scores: dict[str, float]) -> EvalVerdict:
    """Build an EvalVerdict with the given label and per-dimension scores."""
    return EvalVerdict(
        run_id="run-x",
        trial_number=0,
        verdict=verdict,
        dimensions={
            name: DimensionScore(score=score, reason="r", confidence=0.9)
            for name, score in scores.items()
        },
        failure_attribution=None,
        self_evaluation=SelfEvaluation(
            judge_confidence=0.9, self_critique="ok", flag_for_human=False
        ),
        replay_link="https://flight.ahmedxsaad.me/runs/run-x",
        recommended_action="none",
    )


def _window(label: VerdictLabel, score: float, n: int = 4) -> list[EvalVerdict]:
    """A window of n identical verdicts (correctness + reasoning_quality = score)."""
    return [_verdict(label, {"correctness": score, "reasoning_quality": score}) for _ in range(n)]


# ─── pass-rate / dimension drift (pure, no embeddings) ─────────────────────────


async def test_pass_rate_drop_is_drift() -> None:
    """A large pass-rate regression is flagged with a negative delta."""
    baseline = _window("pass", 0.9)
    current = _window("fail", 0.4)

    report = await detector.detect_drift(baseline, current)

    assert report.drift_detected is True
    assert report.pass_rate_baseline == 1.0
    assert report.pass_rate_current == 0.0
    assert report.pass_rate_delta == -1.0
    assert "Drift detected" in report.summary


async def test_dimension_shift_without_verdict_change_is_drift() -> None:
    """A quality drop isolated to scores (verdict unchanged) is still drift."""
    baseline = _window("pass", 0.9)
    current = _window("pass", 0.7)  # same pass rate, scores down 0.2 > 0.15 threshold

    report = await detector.detect_drift(baseline, current)

    assert report.pass_rate_delta == 0.0
    assert report.drift_detected is True
    assert report.most_shifted_dimension in {"correctness", "reasoning_quality"}
    assert report.dimension_deltas["correctness"] == pytest.approx(-0.2)


async def test_stable_windows_report_no_drift() -> None:
    """Near-identical windows are below every threshold."""
    baseline = _window("pass", 0.9)
    current = _window("pass", 0.88)

    report = await detector.detect_drift(baseline, current)

    assert report.drift_detected is False
    assert report.semantic_drift is None
    assert "No meaningful drift" in report.summary


async def test_empty_windows_do_not_crash() -> None:
    """Empty windows yield a zeroed, no-drift report rather than raising."""
    report = await detector.detect_drift([], [])

    assert report.baseline_run_count == 0
    assert report.current_run_count == 0
    assert report.drift_detected is False
    assert report.drift_score == 0.0


# ─── semantic drift (embedding path, monkeypatched) ────────────────────────────


@pytest.fixture
def mock_embed(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install a fake cf_ai_embed mapping each text to a fixed vector."""

    def _install(mapping: dict[str, list[float]]) -> None:
        async def fake_embed(texts: list[str]) -> list[list[float]]:
            return [mapping[text] for text in texts]

        monkeypatch.setattr(cf_ai_client, "cf_ai_embed", fake_embed)

    return _install


async def test_semantic_drift_detected_from_outputs(mock_embed: Any) -> None:
    """Orthogonal baseline/current output centroids cross the semantic threshold."""
    mock_embed({"old": [1.0, 0.0], "new": [0.0, 1.0]})
    baseline = _window("pass", 0.9)
    current = _window("pass", 0.9)  # no score/verdict drift — only semantic

    report = await detector.detect_drift(
        baseline, current, baseline_outputs=["old"], current_outputs=["new"]
    )

    assert report.semantic_drift == pytest.approx(1.0)  # cosine distance of orthogonal vectors
    assert report.drift_detected is True
    assert "semantic drift" in report.summary


async def test_identical_outputs_have_zero_semantic_drift(mock_embed: Any) -> None:
    """Identical output centroids give ~0 distance and no semantic drift."""
    mock_embed({"same": [0.3, 0.4, 0.5]})
    report = await detector.detect_drift(
        _window("pass", 0.9),
        _window("pass", 0.9),
        baseline_outputs=["same"],
        current_outputs=["same"],
    )

    assert report.semantic_drift == pytest.approx(0.0)
    assert report.drift_detected is False


# ─── embedder unit math ────────────────────────────────────────────────────────


def test_centroid_averages_vectors() -> None:
    """_centroid is the element-wise mean."""
    assert embedder._centroid([[0.0, 2.0], [2.0, 4.0]]) == [1.0, 3.0]


def test_cosine_distance_bounds() -> None:
    """Identical → 0, orthogonal → 1; a zero vector is treated as 0 distance."""
    assert embedder.cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)
    assert embedder.cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)
    assert embedder.cosine_distance([0.0, 0.0], [1.0, 1.0]) == 0.0


async def test_embed_centroid_empty_is_none() -> None:
    """No outputs → no centroid (semantic drift stays unavailable)."""
    assert await embedder.embed_centroid([]) is None
