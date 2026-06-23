#!/usr/bin/env python3
"""
run_synthetic_eval.py — Run the Sentinel evaluation suite on synthetic traces.

Fetches all recorded runs from the flight recorder, evaluates each one
using the eval engine (k independent trials), and writes a Markdown
evaluation report to docs/eval_report.md.

Usage:
    make eval
    # or directly:
    python scripts/run_synthetic_eval.py --k 8 --output docs/eval_report.md

Requires: the eval-engine (:8000) and flight-recorder (:8001) services running,
plus CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN in .env (the LLM judge calls
CF Workers AI; there is no Anthropic key in this stack).
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    # python-dotenv is optional: on the VM the services already have their env
    # (systemd EnvironmentFile) and this script only talks to them over localhost,
    # so there is nothing to load from a repo-root .env.
    pass

EVAL_API    = os.environ.get("EVAL_API_URL", "http://localhost:8000")
FLIGHT_API  = os.environ.get("FLIGHT_API_URL", "http://localhost:8001")
REPORT_PATH = "docs/eval_report.md"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    run_id: str
    task_id: str
    trials: list[dict] = field(default_factory=list)

    @property
    def pass_at_1(self) -> bool:
        return any(t["verdict"] == "pass" for t in self.trials)

    @property
    def pass_at_k(self) -> bool:
        return all(t["verdict"] == "pass" for t in self.trials)

    @property
    def consistency_rate(self) -> float:
        if not self.trials:
            return 0.0
        return sum(1 for t in self.trials if t["verdict"] == "pass") / len(self.trials)

    @property
    def mean_score(self) -> float:
        scores = [t.get("score", 0.0) for t in self.trials]
        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class EvalReport:
    total_tasks: int = 0
    total_trials: int = 0
    pass_at_1_count: int = 0
    pass_at_k_count: int = 0
    flagged_for_human: int = 0
    position_bias_flips: int = 0
    dimension_scores: dict = field(default_factory=dict)
    failure_attributions: dict = field(default_factory=dict)
    run_results: list[RunResult] = field(default_factory=list)

    @property
    def pass_at_1_rate(self) -> float:
        return self.pass_at_1_count / self.total_tasks if self.total_tasks else 0.0

    @property
    def pass_at_k_rate(self) -> float:
        return self.pass_at_k_count / self.total_tasks if self.total_tasks else 0.0

    @property
    def consistency_rate(self) -> float:
        if not self.run_results:
            return 0.0
        return sum(r.consistency_rate for r in self.run_results) / len(self.run_results)


# ── API Helpers ───────────────────────────────────────────────────────────────

def get_all_runs() -> list[dict]:
    """Fetch all recorded runs from the flight recorder.

    The flight recorder ``GET /runs`` returns a bare JSON array of manifest rows
    (not an object with a ``runs`` key), so the response is used directly.
    """
    r = requests.get(f"{FLIGHT_API}/runs")
    r.raise_for_status()
    payload = r.json()
    # Tolerate both shapes: a bare list (current API) or {"runs": [...]}.
    return payload["runs"] if isinstance(payload, dict) else payload


def evaluate_run(run_id: str, k: int) -> list[dict]:
    """Evaluate a run k times and return all trial verdicts."""
    verdicts = []
    for trial in range(k):
        r = requests.post(f"{EVAL_API}/evaluate", json={
            "run_id": run_id,
            "trial_number": trial + 1,
        })
        r.raise_for_status()
        verdicts.append(r.json())
        time.sleep(0.1)  # avoid overwhelming the eval API
    return verdicts


def fetch_drift(baseline: list[dict], current: list[dict]) -> dict | None:
    """Ask the eval engine to compare two windows of verdicts (UC1 §2.3).

    Returns the ``DriftReport`` JSON, or ``None`` if the endpoint is unavailable or
    there is not enough data — the report degrades to a note rather than failing.
    """
    if not baseline or not current:
        return None
    try:
        r = requests.post(f"{EVAL_API}/drift", json={"baseline": baseline, "current": current})
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _cohen_kappa(predicted: list[str], gold: list[str]) -> float:
    """Chance-corrected agreement between predicted and gold verdicts (self-contained)."""
    n = len(gold)
    if n == 0:
        return 0.0
    observed = sum(p == g for p, g in zip(predicted, gold, strict=True)) / n
    labels = set(predicted) | set(gold)
    expected = sum((predicted.count(label) / n) * (gold.count(label) / n) for label in labels)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def compute_evaluator_quality(
    run_results: list[RunResult], gold_map: dict[str, str]
) -> dict | None:
    """Score the evaluator against human gold labels (UC1 §2.4).

    ``gold_map`` maps a ``run_id`` or ``task_id`` to its expected verdict. The
    evaluator's first-trial verdict is compared to the gold label; returns accuracy
    and Cohen's κ, or ``None`` when no run could be matched to a gold label.
    """
    predicted: list[str] = []
    gold: list[str] = []
    for r in run_results:
        expected = gold_map.get(r.run_id) or gold_map.get(r.task_id)
        if not expected or not r.trials:
            continue
        predicted.append(r.trials[0].get("verdict", "uncertain"))
        gold.append(expected)
    if not gold:
        return None
    agreements = sum(p == g for p, g in zip(predicted, gold, strict=True))
    return {
        "n_cases": len(gold),
        "n_agreements": agreements,
        "accuracy": agreements / len(gold),
        "cohen_kappa": _cohen_kappa(predicted, gold),
    }


# ── Report Generator ──────────────────────────────────────────────────────────

def _drift_section(drift: dict | None) -> list[str]:
    """Render the behavioural-drift section (UC1 §2.3)."""
    lines = ["## Behavioural Drift (baseline vs current)", ""]
    if not drift:
        lines += [
            "_Not enough data: drift compares two windows of evaluated runs via the eval",
            "engine `POST /drift`. Re-run with more recorded runs (and the service up)._",
            "",
        ]
        return lines
    sem = drift.get("semantic_drift")
    lines += [
        "| Signal | Value |",
        "|---|---|",
        f"| Drift detected | {'YES' if drift.get('drift_detected') else 'no'} |",
        f"| Pass rate (baseline -> current) | {drift.get('pass_rate_baseline', 0):.0%}"
        f" -> {drift.get('pass_rate_current', 0):.0%} ({drift.get('pass_rate_delta', 0):+.0%}) |",
        f"| Most shifted dimension | {drift.get('most_shifted_dimension') or 'n/a'} |",
        f"| Semantic output drift | {'n/a' if sem is None else f'{sem:.2f}'} |",
        f"| Drift score | {drift.get('drift_score', 0):.2f} |",
        "",
        f"> {drift.get('summary', '')}",
        "",
    ]
    return lines


def _evaluator_quality_section(quality: dict | None) -> list[str]:
    """Render the evaluation-of-the-evaluator section (UC1 §2.4)."""
    lines = ["## Evaluation of the Evaluator (judge vs human)", ""]
    if not quality:
        lines += [
            "_No gold labels supplied. Pass `--gold <file.json>` mapping each `run_id` or",
            "`task_id` to its human verdict (pass/fail/uncertain) to report judge-vs-human",
            "agreement (accuracy + Cohen's kappa)._",
            "",
        ]
        return lines
    lines += [
        "| Metric | Value |",
        "|---|---|",
        f"| Gold cases | {quality['n_cases']} |",
        f"| Agreements | {quality['n_agreements']}/{quality['n_cases']} |",
        f"| Accuracy | {quality['accuracy']:.1%} |",
        f"| **Cohen's kappa** (chance-corrected) | **{quality['cohen_kappa']:.2f}** |",
        "",
        "> Cohen's kappa is the headline: it corrects for chance agreement, so a judge",
        "> that always returns one verdict cannot score well on an imbalanced gold set.",
        "",
    ]
    return lines


def generate_report(
    report: EvalReport,
    k: int,
    output_path: str,
    drift: dict | None = None,
    evaluator_quality: dict | None = None,
) -> None:
    """Write the evaluation report to a Markdown file."""
    lines = [
        "# Sentinel — Evaluation Report",
        "",
        f"> Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"> k (trials per task): {k}",
        "",
        "---",
        "",
        "## Primary Metric: pass^k Reliability",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| **pass@1** (≥1 trial passed) | {report.pass_at_1_rate:.1%} |",
        f"| **pass^{k}** (all {k} trials passed) | {report.pass_at_k_rate:.1%} |",
        f"| **Consistency rate** (avg passing trials) | {report.consistency_rate:.1%} |",
        f"| **Total tasks** | {report.total_tasks} |",
        f"| **Total trials** | {report.total_trials} |",
        "",
        "---",
        "",
        "## Per-Dimension Scores",
        "",
        "| Dimension | Mean Score | Pass Rate (≥0.7) |",
        "|---|---|---|",
    ]

    for dim, scores in report.dimension_scores.items():
        if scores:
            mean = sum(scores) / len(scores)
            pass_rate = sum(1 for s in scores if s >= 0.7) / len(scores)
            lines.append(f"| {dim.title()} | {mean:.2f} | {pass_rate:.1%} |")

    lines += [
        "",
        "---",
        "",
        "## Judge Calibration",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Position-bias flips detected | {report.position_bias_flips} |",
        f"| Verdicts flagged for human review | {report.flagged_for_human} |",
        "",
        "---",
        "",
        "## Non-Determinism Handling",
        "",
        f"Each of the {report.total_tasks} tasks was evaluated {k} independent times.",
        f"pass^{k} = {report.pass_at_k_rate:.1%} means only {report.pass_at_k_count} tasks",
        f"passed ALL {k} trials consistently.",
        "",
        "Judge calibration: every LLM judgment was run twice with swapped response ordering.",
        f"Position-bias was detected in {report.position_bias_flips} cases (flipped verdict on swap).",
        "These were marked 'uncertain' and flagged for human review.",
        "",
        "---",
        "",
    ]

    lines += _drift_section(drift)
    lines += ["---", ""]
    lines += _evaluator_quality_section(evaluator_quality)
    lines += [
        "---",
        "",
        f"_Generated by scripts/run_synthetic_eval.py · Sentinel_",
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"\n✓ Report written to {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Sentinel eval suite")
    parser.add_argument("--k",      type=int, default=8,           help="Number of trials per task")
    parser.add_argument("--output", type=str, default=REPORT_PATH, help="Output report path")
    parser.add_argument("--limit",  type=int, default=None,        help="Limit number of runs (for testing)")
    parser.add_argument("--gold", type=str, default=None, help="JSON: run_id/task_id -> verdict")
    args = parser.parse_args()

    gold_map: dict[str, str] = {}
    if args.gold:
        try:
            with open(args.gold) as f:
                gold_map = json.load(f)
        except (OSError, ValueError) as e:
            print(f"WARN: could not read --gold {args.gold}: {e}")

    print(f"=== Sentinel Eval Suite (k={args.k}) ===")
    print(f"Eval API:   {EVAL_API}")
    print(f"Flight API: {FLIGHT_API}")
    print()

    runs = get_all_runs()
    if args.limit:
        runs = runs[:args.limit]

    print(f"Found {len(runs)} recorded runs to evaluate.")

    report = EvalReport()

    for i, run in enumerate(runs, 1):
        run_id = run["run_id"]
        task_id = run.get("task_id", run_id)
        print(f"[{i:3d}/{len(runs)}] Evaluating run {run_id[:8]}... ", end="", flush=True)

        try:
            verdicts = evaluate_run(run_id, args.k)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        result = RunResult(run_id=run_id, task_id=task_id, trials=verdicts)
        report.run_results.append(result)
        report.total_tasks  += 1
        report.total_trials += len(verdicts)

        if result.pass_at_1:
            report.pass_at_1_count += 1
        if result.pass_at_k:
            report.pass_at_k_count += 1

        for verdict in verdicts:
            if verdict.get("flag_for_human"):
                report.flagged_for_human += 1
            if verdict.get("position_bias_detected"):
                report.position_bias_flips += 1
            for dim, score_data in verdict.get("dimensions", {}).items():
                report.dimension_scores.setdefault(dim, []).append(score_data.get("score", 0.0))

        status = "✓" if result.pass_at_k else "✗"
        print(f"{status} pass^{args.k}={result.pass_at_k} consistency={result.consistency_rate:.0%}")

    print()
    print("=== Summary ===")
    print(f"  pass@1:   {report.pass_at_1_rate:.1%}")
    print(f"  pass^{args.k}:  {report.pass_at_k_rate:.1%}")
    print(f"  consistency: {report.consistency_rate:.1%}")

    # Drift: split the evaluated runs into a baseline (older half) vs current (newer
    # half) window and compare their first-trial verdicts via the eval engine.
    first_trials = [r.trials[0] for r in report.run_results if r.trials]
    mid = len(first_trials) // 2
    drift = fetch_drift(first_trials[:mid], first_trials[mid:]) if mid else None

    # Evaluator quality: score the judge against human gold labels, if supplied.
    evaluator_quality = compute_evaluator_quality(report.run_results, gold_map)

    generate_report(report, args.k, args.output, drift, evaluator_quality)


if __name__ == "__main__":
    main()
