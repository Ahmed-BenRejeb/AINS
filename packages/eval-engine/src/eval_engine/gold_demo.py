"""A small, self-contained gold set for the evaluation-of-the-evaluator demo (UC1 §2.4).

Pairs a handful of synthetic agent runs with the verdict a human reviewer would
assign, so the evaluator can be scored against ground truth (Cohen's κ) without
depending on live recorded runs. Two cases are clearly-good (a coherent RCA that
creates the Jira issue → expected ``pass``) and two are clearly-bad (a tool error /
a create-issue step that produced no issue → expected ``fail``). Re-judging these is
cheap (a handful of CF calls), so the dashboard runs it on demand.
"""

from __future__ import annotations

from typing import Any

from trace_core import TraceRecord

from .models import GoldCase

_GENESIS = "sha256:" + "0" * 64


def _record(
    seq: int, kind: str, inp: dict[str, Any], out: dict[str, Any], meta: dict[str, Any]
) -> TraceRecord:
    """Build a minimal valid TraceRecord (audit fields are placeholders for the gold set)."""
    return TraceRecord.model_validate(
        {
            "run_id": f"gold-{seq}",
            "step_id": f"{seq:032d}",
            "sequence": seq,
            "timestamp": "2026-06-23T00:00:00+00:00",
            "kind": kind,
            "input": inp,
            "output": out,
            "metadata": meta,
            "audit": {"prev_hash": _GENESIS, "payload_hash": _GENESIS, "hmac": "0" * 8},
        }
    )


def _good_case(run_id: str, incident: str, summary: str) -> GoldCase:
    """A coherent run that retrieves, reasons, and creates the issue → expected pass."""
    return GoldCase(
        run_id=run_id,
        expected="pass",
        records=[
            _record(
                0,
                "llm_call",
                {"messages": [{"role": "user", "content": f"incident: {incident}"}]},
                {
                    "response": f"Root cause identified for: {incident}. Plan: link runbook, "
                    "file the issue.",
                    "usage": {"total_tokens": 140},
                },
                {"model_id": "@cf/meta/llama-3.1-8b-instruct-fp8-fast"},
            ),
            _record(
                1,
                "tool_call",
                {"tool": "create_jira_issue", "arguments": {"project": "AO", "summary": summary}},
                {"key": "AO-900", "id": "10900", "success": True},
                {"tool_name": "create_jira_issue", "tool_version": "2.1"},
            ),
        ],
    )


def _bad_case(run_id: str, reason: str, output: dict[str, Any]) -> GoldCase:
    """A run whose tool step errored / created nothing → expected fail."""
    return GoldCase(
        run_id=run_id,
        expected="fail",
        records=[
            _record(
                0,
                "llm_call",
                {"messages": [{"role": "user", "content": reason}]},
                {"response": "Attempting remediation.", "usage": {"total_tokens": 90}},
                {"model_id": "@cf/meta/llama-3.1-8b-instruct-fp8-fast"},
            ),
            _record(
                1,
                "tool_call",
                {"tool": "create_jira_issue", "arguments": {"project": "AO", "summary": reason}},
                output,
                {"tool_name": "create_jira_issue", "tool_version": "2.1"},
            ),
        ],
    )


def demo_gold_set() -> list[GoldCase]:
    """The built-in gold set: 2 expected-pass + 2 expected-fail cases."""
    return [
        _good_case("gold-pass-1", "DB connection pool exhausted on prod", "DB pool exhaustion"),
        _good_case("gold-pass-2", "Memory leak after 48h uptime", "Memory leak"),
        # Tool returned an error → the run failed even though it 'looked busy'.
        _bad_case(
            "gold-fail-1", "Disk full on node-7", {"error": "permission denied", "success": False}
        ),
        # Create-issue step produced no key/id → outcome verification fails.
        _bad_case("gold-fail-2", "Cert expired on gateway", {"success": True}),
    ]
