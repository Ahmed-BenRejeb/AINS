"""Local result models for the eval engine's grader pipeline.

These are intermediate types produced by individual graders before the reporter
assembles them into a :class:`trace_core.EvalVerdict`. They are package-internal
(not cross-package), so they live here rather than in ``trace-core``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from trace_core import DimensionScore, TraceRecord, VerdictLabel


class SafetyResult(BaseModel):
    """Outcome of the Llama Guard safety pre-filter."""

    safe: bool = Field(description="True if the content cleared the safety filter.")
    score: float = Field(ge=0.0, le=1.0, description="Safety score in [0, 1]; 1.0 = clearly safe.")
    categories: list[str] = Field(
        default_factory=list,
        description="Llama Guard hazard categories that fired (e.g. 'S1'); empty when safe.",
    )


class CodeGraderResult(BaseModel):
    """Outcome of the fast deterministic code grader."""

    passed: bool = Field(description="True if every deterministic check passed.")
    failures: list[str] = Field(
        default_factory=list, description="Human-readable description of each failed check."
    )
    score: float = Field(
        ge=0.0, le=1.0, description="Fraction of deterministic checks that passed, in [0, 1]."
    )


class JudgeVerdict(BaseModel):
    """Outcome of the calibrated LLM-as-judge."""

    verdict: VerdictLabel = Field(description="pass / fail / uncertain (uncertain = bias flip).")
    dimensions: dict[str, DimensionScore] = Field(
        description="Per-dimension rubric scores keyed by dimension name."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="The judge's overall confidence in its verdict, in [0, 1]."
    )
    self_critique: str = Field(description="The judge's critique of its own reasoning.")
    flag_for_human: bool = Field(
        default=False,
        description="True when the verdict needs human review (low conf / bias flip).",
    )
    reason: str | None = Field(
        default=None,
        description="Why the verdict is uncertain/flagged (e.g. 'position_bias_detected').",
    )


class GoldCase(BaseModel):
    """One human-labelled run in the evaluator-quality gold set (UC1 §2.4).

    Pairs a recorded run with the verdict a human reviewer assigned, so the
    evaluator's own output can be scored against ground truth.
    """

    run_id: str = Field(description="UUID of the gold-labelled run.")
    expected: VerdictLabel = Field(description="The human gold verdict (pass/fail/uncertain).")
    records: list[TraceRecord] = Field(description="The run's ordered TraceRecord steps.")
