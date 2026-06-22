"""Assemble grader outputs into a final ``EvalVerdict`` (and file a Jira issue).

The reporter is the orchestrator for one trial: it runs the safety pre-filter,
the deterministic code grader, and the calibrated LLM judge, combines them into a
single :class:`trace_core.EvalVerdict` with failure attribution and
self-evaluation, and — when the verdict fails or is flagged for human review —
files an Incident in the AO Jira project.
"""

from __future__ import annotations

import logging

from trace_core import (
    CONFIDENCE_THRESHOLD,
    DimensionScore,
    EvalVerdict,
    FailureAttribution,
    SelfEvaluation,
    TraceRecord,
    VerdictLabel,
)

from ..attribution.dag_attributor import attribute_failure
from ..config import replay_link
from ..graders import code_grader
from ..graders.llm_judge import DEFAULT_RUBRIC, calibrated_judge
from ..graders.safety_filter import check_safety
from ..models import CodeGraderResult, JudgeVerdict
from ..transcript import build_transcript
from ..verdict_store import persist_verdict
from . import atlassian_client

logger = logging.getLogger("eval_engine.verdicts.reporter")

_SAFETY_COMPONENT = "safety"


def _combine_verdict(code_result: CodeGraderResult, judge: JudgeVerdict) -> VerdictLabel:
    """Fold the code grader and judge into one verdict label.

    Order of precedence: a judge ``uncertain`` (position-bias flip) wins; then any
    hard failure from either grader; otherwise ``pass``.
    """
    if judge.verdict == "uncertain":
        return "uncertain"
    if not code_result.passed or judge.verdict == "fail":
        return "fail"
    return "pass"


def _recommended_action(verdict: VerdictLabel, attribution: FailureAttribution | None) -> str:
    """Concrete next step for a human, tailored to the verdict."""
    if verdict == "pass":
        return "No action — run passed safety, code, and judge graders."
    if verdict == "uncertain":
        return "Judge verdict is order-sensitive (position bias); human review required."
    if attribution is not None:
        return (
            f"Open the replay and bisect step {attribution.step} "
            f"({attribution.component}): {attribution.description}"
        )
    return "Open the replay and inspect the run."


async def evaluate_run(
    run_id: str,
    trial_number: int,
    records: list[TraceRecord],
    *,
    rubric: str = DEFAULT_RUBRIC,
    file_issue: bool = True,
) -> EvalVerdict:
    """Evaluate one trial of a run and produce a complete ``EvalVerdict``.

    Pipeline: safety pre-filter (short-circuits to ``fail`` if unsafe) → code
    grader → calibrated LLM judge → attribution + self-evaluation. Files a Jira
    Incident when the verdict is ``fail`` or human review is flagged.

    Args:
        run_id: UUID of the run being evaluated.
        trial_number: 0-based trial index within a ``pass^k`` batch.
        records: The run's ordered ``TraceRecord`` steps.
        rubric: Scoring rubric for the judge.
        file_issue: When ``True``, file a Jira issue on fail/flag.

    Returns:
        The assembled :class:`trace_core.EvalVerdict`.
    """
    transcript = build_transcript(records)
    safety = await check_safety(transcript)
    code_result = code_grader.grade(records)

    if not safety.safe:
        # Short-circuit: do not spend a judge call on unsafe content.
        verdict: VerdictLabel = "fail"
        flagged = ", ".join(safety.categories) or "unsafe"
        dimensions = {
            _SAFETY_COMPONENT: DimensionScore(
                score=0.0,
                reason=f"Llama Guard flagged categories: {flagged}",
                confidence=1.0,
            )
        }
        judge_confidence = 1.0
        self_critique = "Safety pre-filter rejected the transcript; judge was skipped."
        flag_for_human = False
    else:
        judge = await calibrated_judge(transcript, rubric)
        verdict = _combine_verdict(code_result, judge)
        dimensions = judge.dimensions
        judge_confidence = judge.confidence
        self_critique = judge.self_critique
        flag_for_human = judge.flag_for_human or judge_confidence < CONFIDENCE_THRESHOLD

    attribution = attribute_failure(records) if verdict != "pass" else None
    self_evaluation = SelfEvaluation(
        judge_confidence=judge_confidence,
        self_critique=self_critique,
        flag_for_human=flag_for_human,
    )

    eval_verdict = EvalVerdict(
        run_id=run_id,
        trial_number=trial_number,
        verdict=verdict,
        dimensions=dimensions,
        failure_attribution=attribution,
        self_evaluation=self_evaluation,
        replay_link=replay_link(run_id),
        recommended_action=_recommended_action(verdict, attribution),
    )

    # Persist the verdict to D1 (best-effort): the durable record the dashboard
    # verdict screens read. A D1 failure must never fail evaluation.
    persist_verdict(eval_verdict)

    if file_issue and (verdict == "fail" or flag_for_human):
        await _file_issue(eval_verdict)
    return eval_verdict


async def _file_issue(verdict: EvalVerdict) -> None:
    """File a Jira Incident summarising a failed/flagged verdict (best-effort).

    The verdict is the product; filing the issue is a side effect. A Jira outage
    or rejection (e.g. a misconfigured project) must never fail evaluation — which
    would null the ``eval_verdict`` in the caller's ``/analyze`` response — so every
    error here is logged and swallowed.
    """
    summary = (
        f"Sentinel eval {verdict.verdict}: {verdict.run_id[:8]} (trial {verdict.trial_number})"
    )
    description = (
        f"Verdict: {verdict.verdict}\n"
        f"Recommended action: {verdict.recommended_action}\n"
        f"Replay: {verdict.replay_link}\n"
        f"Judge confidence: {verdict.self_evaluation.judge_confidence:.2f}\n"
        f"Self-critique: {verdict.self_evaluation.self_critique}"
    )
    try:
        await atlassian_client.create_eval_issue(summary, description)
    except Exception as exc:  # best-effort: a Jira failure must not fail evaluation
        logger.warning("failed to file eval Jira issue for run %s: %s", verdict.run_id, exc)
