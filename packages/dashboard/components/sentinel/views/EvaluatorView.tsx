"use client";

import { useState } from "react";
import { Scale, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { PageTransition } from "../motion";
import { PageHeader } from "../PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { EvaluatorQuality, Loaded } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Evaluation-of-the-evaluator screen (UC1 §2.4). Runs the evaluator over a built-in
 * human-labelled gold set and reports judge-vs-human agreement as accuracy AND
 * Cohen's kappa (chance-corrected). Button-triggered: it re-judges a few cases.
 */
export function EvaluatorView({ mock }: { mock: boolean }) {
  const [result, setResult] = useState<Loaded<EvaluatorQuality> | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`/api/evaluator-quality${mock ? "?mock=true" : ""}`);
      setResult((await res.json()) as Loaded<EvaluatorQuality>);
    } finally {
      setLoading(false);
    }
  }

  const q = result?.data;
  return (
    <PageTransition className="mx-auto w-full max-w-[1180px] space-y-6 px-5 py-10 md:px-8">
      <PageHeader
        title="Evaluator quality"
        subtitle="Judge vs human gold labels (Cohen's kappa)"
        backHref={mock ? "/?mock=true" : "/"}
        backLabel="Overview"
      />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-muted-foreground" aria-hidden />
            Evaluation of the evaluator
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            We do not just LLM-judge - we measure how trustworthy the judge itself is. The
            evaluator runs over a small human-labelled gold set; agreement is reported as raw
            accuracy and, more honestly, as{" "}
            <span className="font-medium text-foreground">Cohen&apos;s kappa</span> (chance-corrected,
            so a judge that always says &quot;pass&quot; on a mostly-passing set scores near zero). This
            re-judges a few cases, so it runs on demand.
          </p>
          <Button onClick={run} disabled={loading} variant="emerald">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Scale className="h-4 w-4" aria-hidden />
            )}
            {loading ? "Scoring the evaluator..." : "Run evaluator-quality check"}
          </Button>

          {q && (
            <div className="space-y-4">
              <div
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium",
                  q.cohen_kappa >= 0.6
                    ? "border-verdict-pass/40 bg-verdict-pass/[0.08] text-verdict-pass"
                    : "border-verdict-uncertain/40 bg-verdict-uncertain/[0.08] text-verdict-uncertain",
                )}
              >
                {q.cohen_kappa >= 0.6 ? (
                  <CheckCircle2 className="h-4 w-4" aria-hidden />
                ) : (
                  <AlertTriangle className="h-4 w-4" aria-hidden />
                )}
                {q.summary}
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric label="Cohen's kappa" value={q.cohen_kappa.toFixed(2)} accent />
                <Metric label="Accuracy" value={`${Math.round(q.accuracy * 100)}%`} />
                <Metric label="Agreement band" value={q.agreement_band} />
                <Metric label="Cases" value={`${q.n_agreements}/${q.n_cases}`} />
              </div>
              <div className="rounded-lg border border-hairline bg-card p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Per-label recall
                </div>
                <div className="mt-2 flex flex-wrap gap-4 font-mono text-sm">
                  {Object.entries(q.per_label_recall).map(([label, recall]) => (
                    <span key={label} className="tabular-nums">
                      <span className="capitalize text-muted-foreground">{label}</span>:{" "}
                      {Math.round(recall * 100)}%
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </PageTransition>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-md border border-hairline bg-canvas px-3 py-2.5">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 font-mono text-xl font-semibold tabular-nums",
          accent ? "text-accent" : "text-foreground",
        )}
      >
        {value}
      </div>
    </div>
  );
}
