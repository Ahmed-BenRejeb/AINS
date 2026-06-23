import { PageHeader } from "@/components/sentinel/PageHeader";
import { PageTransition } from "@/components/sentinel/motion";
import { DriftPanel } from "@/components/sentinel/DriftPanel";
import { EvaluatorQualityPanel } from "@/components/sentinel/EvaluatorQualityPanel";
import type { DataSource, DriftReport, EvaluatorQuality } from "@/lib/types";

/**
 * Reliability-over-time screen: the two UC1 "trust the evaluator over time" signals
 * side by side. Behavioural drift (did the agent's results shift across runs?) and
 * evaluator quality (does the judge agree with human gold verdicts?).
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
      <div className="grid gap-6 lg:grid-cols-2">
        <DriftPanel report={drift} />
        <EvaluatorQualityPanel report={quality} />
      </div>
    </PageTransition>
  );
}
