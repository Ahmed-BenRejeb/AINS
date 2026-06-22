"""Evaluator-quality metric tests (UC1 §2.4) — judge-vs-human agreement / Cohen's κ."""

from __future__ import annotations

import pytest
from eval_engine.metrics.evaluator_quality import (
    agreement_band,
    cohen_kappa,
    score_evaluator,
)
from eval_engine.models import GoldCase
from eval_engine.verdicts import reporter
from trace_core import (
    DimensionScore,
    EvalVerdict,
    SelfEvaluation,
    VerdictLabel,
)

# ─── Cohen's κ math ────────────────────────────────────────────────────────────


def test_perfect_agreement_is_one() -> None:
    """Identical verdicts over >1 label give κ = 1.0."""
    assert cohen_kappa(["pass", "fail", "pass"], ["pass", "fail", "pass"]) == 1.0


def test_chance_level_agreement_is_zero() -> None:
    """50% accuracy that is fully explained by chance gives κ = 0.0."""
    predicted: list[VerdictLabel] = ["pass", "pass", "fail", "fail"]
    gold: list[VerdictLabel] = ["pass", "fail", "fail", "pass"]
    assert cohen_kappa(predicted, gold) == pytest.approx(0.0)


def test_substantial_example() -> None:
    """8/10 correct, balanced labels → κ = 0.6 (chance-corrected below accuracy)."""
    # 5 pass + 5 fail gold; the evaluator misses exactly one of each class.
    gold: list[VerdictLabel] = [
        "pass",
        "pass",
        "pass",
        "pass",
        "pass",
        "fail",
        "fail",
        "fail",
        "fail",
        "fail",
    ]
    predicted: list[VerdictLabel] = [
        "pass",
        "pass",
        "pass",
        "pass",
        "fail",
        "fail",
        "fail",
        "fail",
        "fail",
        "pass",
    ]
    assert cohen_kappa(predicted, gold) == pytest.approx(0.6)


def test_empty_is_zero() -> None:
    """No cases → κ = 0.0 (cannot measure agreement)."""
    assert cohen_kappa([], []) == 0.0


def test_constant_identical_is_one() -> None:
    """All-pass predicted vs all-pass gold → κ = 1.0 (no disagreement to correct)."""
    assert cohen_kappa(["pass", "pass"], ["pass", "pass"]) == 1.0


def test_length_mismatch_raises() -> None:
    """Mismatched lengths are a programming error, not a 0 score."""
    with pytest.raises(ValueError):
        cohen_kappa(["pass"], ["pass", "fail"])


def test_agreement_band_thresholds() -> None:
    """κ maps to the Landis & Koch qualitative bands."""
    assert agreement_band(-0.1) == "poor"
    assert agreement_band(0.0) == "poor"
    assert agreement_band(0.5) == "moderate"
    assert agreement_band(0.6) == "moderate"  # 0.60 boundary is still moderate
    assert agreement_band(0.7) == "substantial"
    assert agreement_band(0.95) == "almost perfect"


# ─── score_evaluator report ────────────────────────────────────────────────────


def test_score_evaluator_builds_report() -> None:
    """The report carries accuracy, κ, per-label recall, band, and a summary."""
    predicted: list[VerdictLabel] = ["pass", "pass", "fail", "fail"]
    gold: list[VerdictLabel] = ["pass", "fail", "fail", "pass"]

    report = score_evaluator(predicted, gold)

    assert report.n_cases == 4
    assert report.n_agreements == 2
    assert report.accuracy == 0.5
    assert report.cohen_kappa == pytest.approx(0.0)
    assert report.agreement_band == "poor"
    assert report.per_label_recall == {"fail": 0.5, "pass": 0.5}
    assert "2/4" in report.summary


def test_score_evaluator_empty() -> None:
    """An empty gold set yields a zeroed report, not a crash."""
    report = score_evaluator([], [])

    assert report.n_cases == 0
    assert report.accuracy == 0.0
    assert report.cohen_kappa == 0.0
    assert report.summary == "No gold cases to score."


# ─── evaluate_gold_set orchestration ───────────────────────────────────────────


def _verdict(label: VerdictLabel) -> EvalVerdict:
    """A minimal EvalVerdict carrying just the verdict label."""
    return EvalVerdict(
        run_id="r",
        trial_number=0,
        verdict=label,
        dimensions={"correctness": DimensionScore(score=0.5, reason="r", confidence=0.9)},
        failure_attribution=None,
        self_evaluation=SelfEvaluation(
            judge_confidence=0.9, self_critique="ok", flag_for_human=False
        ),
        replay_link="https://flight.ahmedxsaad.me/runs/r",
        recommended_action="none",
    )


async def test_evaluate_gold_set_scores_against_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """evaluate_gold_set runs the evaluator per case and scores agreement vs gold."""
    # The evaluator returns the verdict keyed by run_id (agrees on g1/g2, errs on g3).
    predictions = {"g1": "pass", "g2": "fail", "g3": "pass"}

    async def fake_evaluate_run(
        run_id: str, trial_number: int, records: list[object], *, file_issue: bool = True
    ) -> EvalVerdict:
        assert file_issue is False  # gold scoring must never file Jira issues
        return _verdict(predictions[run_id])  # type: ignore[arg-type]

    monkeypatch.setattr(reporter, "evaluate_run", fake_evaluate_run)

    cases = [
        GoldCase(run_id="g1", expected="pass", records=[]),
        GoldCase(run_id="g2", expected="fail", records=[]),
        GoldCase(run_id="g3", expected="fail", records=[]),  # evaluator will say pass
    ]

    report = await reporter.evaluate_gold_set(cases)

    assert report.n_cases == 3
    assert report.n_agreements == 2  # g1, g2 agree; g3 disagrees
    assert report.accuracy == pytest.approx(2 / 3)
