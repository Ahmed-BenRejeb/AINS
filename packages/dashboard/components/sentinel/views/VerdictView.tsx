"use client";

import { PageTransition } from "../motion";
import { PageHeader } from "../PageHeader";
import { VerdictCard } from "../VerdictCard";
import type { DataSource, EvalVerdict } from "@/lib/types";
import { withMock } from "@/lib/utils";

/**
 * Verdict detail screen: a page header (run id + trial) wrapping the full
 * {@link VerdictCard}. Receives the server-fetched verdict and its data-source.
 */
export function VerdictView({
  verdict,
  source,
  sourceError,
  mock,
}: {
  verdict: EvalVerdict;
  source: DataSource;
  sourceError?: string;
  mock: boolean;
}) {
  return (
    <PageTransition className="mx-auto w-full max-w-[1180px] space-y-6 px-5 py-10 md:px-8">
      <PageHeader
        title="Evaluation verdict"
        subtitle={
          <span className="font-mono">
            {verdict.run_id}
            {typeof verdict.trial_number === "number" && (
              <span className="ml-2 text-muted-foreground">trial #{verdict.trial_number}</span>
            )}
          </span>
        }
        source={source}
        sourceError={sourceError}
        backHref={withMock(`/runs/${verdict.run_id}`, mock)}
        backLabel="Back to trace"
      />
      <VerdictCard verdict={verdict} mock={mock} />
    </PageTransition>
  );
}
