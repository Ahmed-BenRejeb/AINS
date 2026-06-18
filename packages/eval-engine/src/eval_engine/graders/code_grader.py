"""Fast, deterministic code grader.

Runs cheap, non-LLM checks over a recorded run *before* the expensive judge:
schema validity, tool-call correctness, outcome verification (did the Jira issue
actually get created?), loop detection, and a token-budget check. These catch the
obvious failures deterministically and feed failure attribution.

A "trace" here is the ordered list of :class:`trace_core.TraceRecord` steps for
one run. The grader is pure and synchronous — no I/O, no LLM.
"""

from __future__ import annotations

from typing import Any

from trace_core import TraceRecord

from ..config import MAX_REPEATED_STEPS, TOKEN_BUDGET
from ..models import CodeGraderResult

# Tool-name fragments that indicate a retrieval/search step.
_RETRIEVAL_HINTS = ("search", "retrieve", "fetch", "vector", "lookup", "query")
# Tool-name fragments that indicate an issue-creating execution step.
_CREATE_ISSUE_HINTS = ("create_issue", "create_jira", "create_incident", "file_issue")


def _is_error_output(output: dict[str, Any]) -> bool:
    """True if a step's output signals an error or an unsuccessful call."""
    if "error" in output and output["error"]:
        return True
    return output.get("success") is False


def _check_schema(records: list[TraceRecord], failures: list[str]) -> None:
    """Each step must carry the provenance its kind requires."""
    for record in records:
        if record.kind == "llm_call" and not record.metadata.model_id:
            failures.append(f"step {record.sequence}: llm_call missing metadata.model_id")
        if record.kind == "tool_call" and not record.metadata.tool_name:
            failures.append(f"step {record.sequence}: tool_call missing metadata.tool_name")


def _check_tool_calls(records: list[TraceRecord], failures: list[str]) -> None:
    """Tool calls must name a tool, carry arguments, and not return an error."""
    for record in records:
        if record.kind != "tool_call":
            continue
        if "arguments" not in record.input and "args" not in record.input:
            failures.append(f"step {record.sequence}: tool_call has no arguments")
        if _is_error_output(record.output):
            tool = record.metadata.tool_name or "?"
            failures.append(f"step {record.sequence}: tool '{tool}' returned an error")


def _check_outcome(records: list[TraceRecord], failures: list[str]) -> None:
    """A create-issue step must produce a real issue key/id (outcome verification)."""
    for record in records:
        tool = (record.metadata.tool_name or "").lower()
        if record.kind == "tool_call" and any(hint in tool for hint in _CREATE_ISSUE_HINTS):
            if not (record.output.get("key") or record.output.get("id")):
                failures.append(
                    f"step {record.sequence}: '{tool}' did not create an issue (no key/id)"
                )


def _check_loops(records: list[TraceRecord], failures: list[str]) -> None:
    """Flag MAX_REPEATED_STEPS+ identical consecutive (kind, input) steps."""
    ordered = sorted(records, key=lambda r: r.sequence)
    run_len = 1
    for prev, curr in zip(ordered, ordered[1:], strict=False):
        same = prev.kind == curr.kind and prev.input == curr.input
        run_len = run_len + 1 if same else 1
        if run_len >= MAX_REPEATED_STEPS:
            failures.append(f"step {curr.sequence}: loop detected ({run_len} identical steps)")
            return


def _check_token_budget(records: list[TraceRecord], failures: list[str]) -> None:
    """Sum reported token usage and flag runs over TOKEN_BUDGET.

    Only steps that report ``output.usage.total_tokens`` count; runs without usage
    data are not penalised (the recorder may not have captured it).
    """
    total = 0
    for record in records:
        usage = record.output.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
            total += usage["total_tokens"]
    if total > TOKEN_BUDGET:
        failures.append(f"token budget exceeded: {total} > {TOKEN_BUDGET}")


# The ordered checks; ``score`` is the fraction of these that pass.
_CHECKS = (
    _check_schema,
    _check_tool_calls,
    _check_outcome,
    _check_loops,
    _check_token_budget,
)


def grade(records: list[TraceRecord]) -> CodeGraderResult:
    """Run all deterministic checks over a run trace.

    Args:
        records: The ordered ``TraceRecord`` steps of one run.

    Returns:
        A :class:`CodeGraderResult`; ``score`` is the fraction of checks that
        produced no failure, ``passed`` is ``True`` only when none did.
    """
    failures_before = 0
    failures: list[str] = []
    checks_passed = 0
    for check in _CHECKS:
        check(records, failures)
        if len(failures) == failures_before:
            checks_passed += 1
        failures_before = len(failures)
    score = checks_passed / len(_CHECKS)
    return CodeGraderResult(passed=not failures, failures=failures, score=score)
