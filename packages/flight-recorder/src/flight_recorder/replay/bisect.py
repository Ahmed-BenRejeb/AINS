"""Find the first diverging step between two recorded runs.

Given a known-good run and a known-bad run, :func:`bisect_runs` walks both
cassettes in recorded order and returns the first position where the requests or
their responses differ — the place to start debugging a regression.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..proxy import cassette


def _extract_rca(loaded: dict[str, Any]) -> str | None:
    """Return the RCA text from the last chat-type step in a cassette.

    Identifies the chat step by the presence of ``result.response`` (a string) as
    opposed to the embed step whose response has ``result.data`` (a float list).
    """
    for step_key in reversed(loaded.get("order", [])):
        step = loaded["steps"].get(step_key, {})
        body = step.get("body")
        if not isinstance(body, dict):
            continue
        result = body.get("result")
        if not isinstance(result, dict):
            continue
        response = result.get("response")
        if isinstance(response, str):
            return response[:1200]
    return None


class BisectResult(BaseModel):
    """Where two runs first diverge (if at all)."""

    good_run_id: str = Field(description="UUID of the known-good run.")
    bad_run_id: str = Field(description="UUID of the known-bad run.")
    identical: bool = Field(description="True if both runs match step for step.")
    first_diverging_step: int | None = Field(
        default=None, description="0-based index of the first differing step (None if identical)."
    )
    reason: str | None = Field(
        default=None, description="What differed at the diverging step (None if identical)."
    )
    good_step_key: str | None = Field(
        default=None, description="Good run's cassette key at the diverging step."
    )
    bad_step_key: str | None = Field(
        default=None, description="Bad run's cassette key at the diverging step."
    )
    good_output: dict[str, Any] | None = Field(
        default=None, description="Good run's recorded response at the diverging step."
    )
    bad_output: dict[str, Any] | None = Field(
        default=None, description="Bad run's recorded response at the diverging step."
    )
    good_rca: str | None = Field(
        default=None,
        description="Full RCA text produced by the good run (from its chat-step cassette response).",
    )
    bad_rca: str | None = Field(
        default=None,
        description="Full RCA text produced by the bad run (from its chat-step cassette response).",
    )


def bisect_runs(good_run_id: str, bad_run_id: str) -> BisectResult:
    """Compare two cassettes step by step and report the first divergence.

    Steps are compared positionally using each cassette's recorded ``order``. A
    step diverges when its request key differs (the agent asked something else)
    or its recorded response differs (the API answered differently). A shorter
    run diverges at the point where the other still has steps.

    Args:
        good_run_id: UUID of the known-good run.
        bad_run_id: UUID of the known-bad run.

    Returns:
        A :class:`BisectResult` pinpointing the first divergence, or marking the
        runs identical.
    """
    good = cassette.load_cassette(good_run_id)
    bad = cassette.load_cassette(bad_run_id)
    good_order: list[str] = good["order"]
    bad_order: list[str] = bad["order"]
    good_rca = _extract_rca(good)
    bad_rca = _extract_rca(bad)

    for index in range(min(len(good_order), len(bad_order))):
        good_key = good_order[index]
        bad_key = bad_order[index]
        good_output = good["steps"][good_key]
        bad_output = bad["steps"][bad_key]
        if good_key != bad_key:
            reason = "request diverged (different step_key)"
        elif good_output != bad_output:
            reason = "response diverged (same request, different output)"
        else:
            continue
        return BisectResult(
            good_run_id=good_run_id,
            bad_run_id=bad_run_id,
            identical=False,
            first_diverging_step=index,
            reason=reason,
            good_step_key=good_key,
            bad_step_key=bad_key,
            good_output=good_output,
            bad_output=bad_output,
            good_rca=good_rca,
            bad_rca=bad_rca,
        )

    if len(good_order) != len(bad_order):
        index = min(len(good_order), len(bad_order))
        return BisectResult(
            good_run_id=good_run_id,
            bad_run_id=bad_run_id,
            identical=False,
            first_diverging_step=index,
            reason="run length diverged (one run has more steps)",
            good_rca=good_rca,
            bad_rca=bad_rca,
        )

    return BisectResult(
        good_run_id=good_run_id,
        bad_run_id=bad_run_id,
        identical=True,
        good_rca=good_rca,
        bad_rca=bad_rca,
    )
