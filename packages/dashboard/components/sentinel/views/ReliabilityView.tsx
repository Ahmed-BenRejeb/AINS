import { ActivitySquare, Gauge } from "lucide-react";
import { PageHeader } from "@/components/sentinel/PageHeader";
import { PageTransition } from "@/components/sentinel/motion";
import { DriftPanel } from "@/components/sentinel/DriftPanel";
import { EvaluatorQualityPanel } from "@/components/sentinel/EvaluatorQualityPanel";
import type { DataSource, DriftReport, EvaluatorQuality } from "@/lib/types";

/**
 * Reliability-over-time screen: drift + evaluator-quality side by side (UC1 §2.3/§2.4).
 */
export function ReliabilityView({
  drift,
  quality,
  source,
  sourceError,
}: {
  drift: DriftReport;
  quality: EvaluatorQuality;
  source: DataSource;
  sourceError?: string;
}) {
  return (
    <PageTransition className="mx-auto w-full max-w-[1180px] space-y-6 px-5 py-10 md:px-8">
      <PageHeader
        title="Reliability over time"
        subtitle="Behavioural drift across runs, and how far the AI judge agrees with human gold verdicts."
        source={source}
        sourceError={sourceError}
        backHref="/"
        backLabel="Overview"
      />

      {/* Context strip — two brief explainers so judges understand the metrics immediately */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex gap-3 rounded-xl border border-hairline bg-surface/50 px-5 py-4">
          <ActivitySquare className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-foreground">
              Drift detection
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
              Splits evaluated runs into a baseline and a current window, compares pass-rate and
              per-dimension score distributions, and measures semantic output shift via BGE
              embedding centroids. Catches silent degradation without ground-truth labels.
            </p>
          </div>
        </div>
        <div className="flex gap-3 rounded-xl border border-hairline bg-surface/50 px-5 py-4">
          <Gauge className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-foreground">
              Evaluator quality
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
              Runs the judge over a human-labelled gold set and reports Cohen&apos;s κ —
              chance-corrected agreement. Raw accuracy flatters a judge that always says{" "}
              <span className="font-mono text-xs text-foreground">pass</span>; κ exposes it.
              Follows AgentRewardBench (arXiv 2504.08942) methodology.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <DriftPanel report={drift} />
        <EvaluatorQualityPanel report={quality} />
      </div>
    </PageTransition>
  );
}
