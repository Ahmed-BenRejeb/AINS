"use client";

import { TrendingDown, TrendingUp, Minus, ArrowRight } from "lucide-react";
import { PageTransition, motion } from "../motion";
import { PageHeader } from "../PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DataSource, DriftReport } from "@/lib/types";
import { cn, pct } from "@/lib/utils";

/**
 * Drift screen (UC1 §2.3): compares an older "baseline" window of evaluated runs
 * against a newer "current" window and shows whether agent behaviour shifted -
 * pass-rate delta, per-dimension deltas, and semantic (output-embedding) drift.
 */
export function DriftView({
  report,
  source,
  sourceError,
  mock,
}: {
  report: DriftReport;
  source: DataSource;
  sourceError?: string;
  mock: boolean;
}) {
  const r = report;
  const dims = Object.entries(r.dimension_deltas).sort(
    (a, b) => Math.abs(b[1]) - Math.abs(a[1]),
  );
  return (
    <PageTransition className="mx-auto w-full max-w-[1180px] space-y-6 px-5 py-10 md:px-8">
      <PageHeader
        title="Behavioural drift"
        subtitle="Baseline (older runs) vs current (newer runs)"
        source={source}
        sourceError={sourceError}
        backHref={mock ? "/?mock=true" : "/"}
        backLabel="Overview"
      />

      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium",
          r.drift_detected
            ? "border-verdict-fail/40 bg-verdict-fail/[0.08] text-verdict-fail"
            : "border-verdict-pass/40 bg-verdict-pass/[0.08] text-verdict-pass",
        )}
      >
        {r.drift_detected ? (
          <TrendingDown className="h-4 w-4" aria-hidden />
        ) : (
          <Minus className="h-4 w-4" aria-hidden />
        )}
        {r.summary}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Pass rate"
          from={pct(r.pass_rate_baseline)}
          to={pct(r.pass_rate_current)}
          delta={r.pass_rate_delta}
        />
        <Stat
          label="Mean score"
          from={r.mean_score_baseline.toFixed(2)}
          to={r.mean_score_current.toFixed(2)}
          delta={r.mean_score_current - r.mean_score_baseline}
        />
        <div className="rounded-lg border border-hairline bg-card p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Semantic drift</div>
          <div className="mt-2 font-mono text-2xl font-semibold tabular-nums">
            {r.semantic_drift === null ? "n/a" : r.semantic_drift.toFixed(2)}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            output-embedding centroid distance
          </div>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Per-dimension shift</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {dims.length === 0 && (
            <p className="text-sm text-muted-foreground">No dimension data in these windows.</p>
          )}
          {dims.map(([name, delta]) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center justify-between rounded-md border border-hairline/60 px-3 py-2"
            >
              <span className="font-mono text-sm capitalize text-foreground/90">
                {name.replace(/_/g, " ")}
                {name === r.most_shifted_dimension && (
                  <span className="ml-2 rounded bg-verdict-uncertain/15 px-1.5 py-0.5 text-[10px] uppercase text-verdict-uncertain">
                    most shifted
                  </span>
                )}
              </span>
              <span
                className={cn(
                  "inline-flex items-center gap-1 font-mono text-sm tabular-nums",
                  delta < -0.01
                    ? "text-verdict-fail"
                    : delta > 0.01
                      ? "text-verdict-pass"
                      : "text-muted-foreground",
                )}
              >
                {delta < -0.01 ? (
                  <TrendingDown className="h-3.5 w-3.5" aria-hidden />
                ) : delta > 0.01 ? (
                  <TrendingUp className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <Minus className="h-3.5 w-3.5" aria-hidden />
                )}
                {delta >= 0 ? "+" : ""}
                {delta.toFixed(2)}
              </span>
            </motion.div>
          ))}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Windows: {r.baseline_run_count} baseline run(s)
        <ArrowRight className="mx-1 inline h-3 w-3" aria-hidden />
        {r.current_run_count} current run(s). A model update can shift output
        characteristics with no pass/fail change - the semantic signal catches what verdict
        drift alone misses (brief Scenario B).
      </p>
    </PageTransition>
  );
}

function Stat({
  label,
  from,
  to,
  delta,
}: {
  label: string;
  from: string;
  to: string;
  delta: number;
}) {
  const down = delta < -0.001;
  return (
    <div className="rounded-lg border border-hairline bg-card p-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-2 flex items-center gap-2 font-mono text-2xl font-semibold tabular-nums">
        <span className="text-muted-foreground">{from}</span>
        <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden />
        <span className={down ? "text-verdict-fail" : "text-foreground"}>{to}</span>
      </div>
    </div>
  );
}
