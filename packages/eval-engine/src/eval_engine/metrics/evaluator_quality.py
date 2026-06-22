"""Evaluation-of-the-evaluator metric (UC1 §2.4).

Scores how well the evaluator agrees with a human-labelled gold set. Raw accuracy
alone is misleading when one verdict label dominates (a judge that always says
"pass" looks great on a mostly-passing set), so the headline metric is **Cohen's κ**
— agreement corrected for what chance alone would produce. This module is pure
statistics (no I/O, like :mod:`pass_at_k`); the orchestration that runs the
evaluator over gold cases lives in :mod:`eval_engine.verdicts.reporter`.
"""

from __future__ import annotations

from trace_core import EvaluatorQuality, VerdictLabel

# Cohen's κ interpretation bands (Landis & Koch, Biometrics 1977). Upper bound of
# each band, ascending; the first band whose bound κ does not exceed names it.
_KAPPA_BANDS: tuple[tuple[float, str], ...] = (
    (0.0, "poor"),
    (0.20, "slight"),
    (0.40, "fair"),
    (0.60, "moderate"),
    (0.80, "substantial"),
    (1.00, "almost perfect"),
)


def agreement_band(kappa: float) -> str:
    """Map a Cohen's κ value to its Landis & Koch qualitative band.

    Args:
        kappa: Cohen's κ in [-1, 1].

    Returns:
        The qualitative agreement band (e.g. ``"substantial"``); ``"poor"`` for any
        κ at or below 0 (chance-level or worse).
    """
    for upper, label in _KAPPA_BANDS:
        if kappa <= upper:
            return label
    return "almost perfect"


def cohen_kappa(predicted: list[VerdictLabel], gold: list[VerdictLabel]) -> float:
    """Cohen's κ between the evaluator's verdicts and the human gold labels.

    κ = (p_o - p_e) / (1 - p_e), where ``p_o`` is observed agreement and ``p_e`` is
    the agreement expected by chance from each rater's label frequencies.

    Args:
        predicted: The evaluator's verdict per case.
        gold: The human gold verdict per case (same length and order).

    Returns:
        Cohen's κ in [-1, 1]: 1 perfect agreement, 0 chance-level, <0 worse than
        chance. Returns 0.0 for an empty set, and 1.0 when both raters are constant
        and identical (no disagreement to chance-correct).

    Raises:
        ValueError: If ``predicted`` and ``gold`` differ in length.
    """
    if len(predicted) != len(gold):
        raise ValueError("predicted and gold must have the same length")
    n = len(gold)
    if n == 0:
        return 0.0

    observed = sum(p == g for p, g in zip(predicted, gold, strict=True)) / n
    labels = set(predicted) | set(gold)
    expected = sum((predicted.count(label) / n) * (gold.count(label) / n) for label in labels)
    if expected == 1.0:
        # Both raters are constant and identical → perfect, no chance correction.
        return 1.0
    return (observed - expected) / (1.0 - expected)


def _per_label_recall(predicted: list[VerdictLabel], gold: list[VerdictLabel]) -> dict[str, float]:
    """Fraction of each gold label the evaluator matched (per-label sensitivity)."""
    recall: dict[str, float] = {}
    for label in sorted(set(gold)):
        total = gold.count(label)
        hits = sum(p == g == label for p, g in zip(predicted, gold, strict=True))
        recall[label] = hits / total if total else 0.0
    return recall


def score_evaluator(predicted: list[VerdictLabel], gold: list[VerdictLabel]) -> EvaluatorQuality:
    """Build an :class:`trace_core.EvaluatorQuality` from predictions vs gold labels.

    Args:
        predicted: The evaluator's verdict per case.
        gold: The human gold verdict per case (same length and order).

    Returns:
        The assembled quality report (accuracy, Cohen's κ, per-label recall, band,
        and a human-readable summary).

    Raises:
        ValueError: If ``predicted`` and ``gold`` differ in length.
    """
    if len(predicted) != len(gold):
        raise ValueError("predicted and gold must have the same length")
    n = len(gold)
    agreements = sum(p == g for p, g in zip(predicted, gold, strict=True))
    accuracy = agreements / n if n else 0.0
    kappa = cohen_kappa(predicted, gold)
    band = agreement_band(kappa)
    summary = (
        f"Evaluator agreed with {agreements}/{n} human gold verdicts "
        f"(accuracy {accuracy:.0%}); Cohen's κ {kappa:.2f} ({band})."
        if n
        else "No gold cases to score."
    )
    return EvaluatorQuality(
        n_cases=n,
        n_agreements=agreements,
        accuracy=accuracy,
        cohen_kappa=kappa,
        per_label_recall=_per_label_recall(predicted, gold),
        agreement_band=band,
        summary=summary,
    )
