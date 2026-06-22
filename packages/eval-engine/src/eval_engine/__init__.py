"""Sentinel eval engine (UC1).

Consumes recorded agent traces and produces auditable :class:`trace_core.EvalVerdict`
objects: a safety pre-filter, a fast deterministic code grader, and a calibrated
LLM-as-judge (position-bias calibration is mandatory), plus DAG failure
attribution, ``pass^k``, and Jira issue reporting on failure.

All LLM calls go through Cloudflare Workers AI (`cf_ai_client`); shared schemas
come from ``trace_core`` and are never redefined here.
"""

from __future__ import annotations

from .drift.detector import detect_drift
from .graders import code_grader
from .graders.llm_judge import calibrated_judge, judge
from .graders.safety_filter import check_safety
from .metrics.evaluator_quality import cohen_kappa, score_evaluator
from .metrics.pass_at_k import consistency_rate, pass_at_k
from .models import CodeGraderResult, GoldCase, JudgeVerdict, SafetyResult
from .verdicts.reporter import evaluate_gold_set, evaluate_run

__all__ = [
    "CodeGraderResult",
    "GoldCase",
    "JudgeVerdict",
    "SafetyResult",
    "calibrated_judge",
    "check_safety",
    "code_grader",
    "cohen_kappa",
    "consistency_rate",
    "detect_drift",
    "evaluate_gold_set",
    "evaluate_run",
    "judge",
    "pass_at_k",
    "score_evaluator",
]
