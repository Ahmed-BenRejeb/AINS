import { ActivitySquare, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DriftReport } from "@/lib/types";
import { cn, pct } from "@/lib/utils";

function signedPts(delta: number): string {
  const sign = delta > 0 ? "+" : delta < 0 ? "-" : "";
  return `${sign}${Math.round(Math.abs(delta) * 100)} pts`;
}

function signedScore(delta: number): string {
  const sign = delta > 0 ? "+" : delta < 0 ? "-" : "";
  return `${sign}${Math.abs(delta).toFixed(2)}`;
}

function RateStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="font-mono text-3xl font-semibold tabular-nums tracking-tight text-foreground">
        {pct(value)}
      </div>
      <div className="mt-1 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
    </div>
  );
}

/**
 * Behavioural-drift report card (UC1 §2.3). Shows pass-rate shift + per-dimension
 * score deltas side-by-side. Designed for the /reliability unified view.
 */
export function DriftPanel({ report }: { report: DriftReport }) {
  const regressed = report.pass_rate_delta < 0;
  const Trend = regressed ? TrendingDown : TrendingUp;
  const dims = Object.entries(report.dimension_deltas).sort(
    (a, b) => Math.abs(b[1]) - Math.abs(a[1]),
  );

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2">
          <ActivitySquare className="h-4 w-4 text-muted-foreground" aria-hidden />
          Behavioural drift
        </CardTitle>
        <Badge variant={report.drift_detected ? "uncertain" : "pass"} className="uppercase tracking-wide">
          {report.drift_detected ? "Drift detected" : "Stable"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-4 rounded-lg border border-hairline bg-surface/40 px-5 py-4">
          <RateStat label={`Baseline · ${report.baseline_run_count} runs`} value={report.pass_rate_baseline} />
          <div className="flex flex-col items-center text-muted-foreground">
            <span className="text-lg leading-none">{"->"}</span>
          </div>
          <RateStat label={`Current · ${report.current_run_count} runs`} value={report.pass_rate_current} />
          <div
            className={cn(
              "ml-auto flex items-center gap-1.5 font-mono text-sm font-medium tabular-nums",
              regressed ? "text-verdict-fail" : "text-verdict-pass",
            )}
          >
            <Trend className="h-4 w-4" aria-hidden />
            {signedPts(report.pass_rate_delta)}
          </div>
        </div>

        <div>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
            Dimension score shift
          </div>
          <div className="space-y-1.5">
            {dims.map(([name, delta]) => {
              const shifted = name === report.most_shifted_dimension;
              return (
                <div key={name} className="flex items-center gap-3 text-sm">
                  <span
                    className={cn(
                      "w-40 shrink-0 truncate",
                      shifted ? "font-medium text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {name.replace(/_/g, " ")}
                  </span>
                  <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
                    <div
                      className={cn(
                        "absolute inset-y-0 rounded-full",
                        delta < 0 ? "bg-verdict-fail right-1/2" : "bg-verdict-pass left-1/2",
                      )}
                      style={{ width: `${Math.min(Math.abs(delta) * 100 * 2, 50)}%` }}
                    />
                    <div className="absolute inset-y-0 left-1/2 w-px bg-hairline-strong" />
                  </div>
                  <span
                    className={cn(
                      "w-14 shrink-0 text-right font-mono tabular-nums text-sm",
                      delta < 0 ? "text-verdict-fail" : delta > 0 ? "text-verdict-pass" : "text-muted-foreground",
                    )}
                  >
                    {signedScore(delta)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {report.semantic_drift !== null && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Semantic output drift</span>
            <span className="font-mono tabular-nums text-foreground">
              {report.semantic_drift.toFixed(3)}
            </span>
          </div>
        )}

        <p className="text-sm leading-relaxed text-muted-foreground">{report.summary}</p>
      </CardContent>
    </Card>
  );
}
