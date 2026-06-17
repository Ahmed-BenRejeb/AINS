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

Requires: LANGFUSE_HOST, CF_D1_DATABASE_ID, ANTHROPIC_API_KEY in .env
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

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
    """Fetch all recorded runs from the flight recorder."""
    r = requests.get(f"{FLIGHT_API}/runs")
    r.raise_for_status()
    return r.json()["runs"]


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


# ── Report Generator ──────────────────────────────────────────────────────────

def generate_report(report: EvalReport, k: int, output_path: str) -> None:
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
    args = parser.parse_args()

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

    generate_report(report, args.k, args.output)


if __name__ == "__main__":
    main()
