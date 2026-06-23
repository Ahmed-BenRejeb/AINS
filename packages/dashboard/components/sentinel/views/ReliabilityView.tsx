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
      <div className="grid gap-6 lg:grid-cols-2">
        <DriftPanel report={drift} />
        <EvaluatorQualityPanel report={quality} />
      </div>
    </PageTransition>
  );
}
