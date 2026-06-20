import { Crosshair } from "lucide-react";
import { ConfidenceBar } from "./ConfidenceBar";
import type { FailureAttribution } from "@/lib/types";

/**
 * Failure attribution: the one box that answers "what broke and where". Renders
 * the blamed step + component prominently, the judge's explanation, and a
 * confidence bar. Styled in the FAIL red so it reads as the post-mortem headline.
 */
export function AttributionBox({ attribution }: { attribution: FailureAttribution }) {
  return (
    <div className="rounded-lg border border-verdict-fail/30 bg-verdict-fail/[0.06] p-5">
      <div className="flex items-center gap-2 text-verdict-fail">
        <Crosshair className="h-4 w-4" aria-hidden />
        <h3 className="text-sm font-semibold uppercase tracking-wide">Failure Attribution</h3>
      </div>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded-md border border-verdict-fail/30 bg-verdict-fail/10 px-2 py-0.5 font-mono text-sm text-verdict-fail">
          Step {attribution.step}
        </span>
        <span className="text-muted-foreground">→</span>
        <span className="font-mono text-sm font-medium text-foreground">
          {attribution.component}
        </span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-foreground/90">{attribution.description}</p>

      <div className="mt-4 flex items-center gap-3">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          Attribution confidence
        </span>
        <ConfidenceBar value={attribution.confidence} className="w-40" />
      </div>
    </div>
  );
}
