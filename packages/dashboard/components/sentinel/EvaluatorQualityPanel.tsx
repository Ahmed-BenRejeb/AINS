import { Gauge } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBar } from "./ConfidenceBar";
import type { EvaluatorQuality } from "@/lib/types";
import { cn, pct } from "@/lib/utils";

function bandTone(band: string): "pass" | "uncertain" | "fail" {
  if (band === "substantial" || band === "almost perfect") return "pass";
  if (band === "moderate" || band === "fair") return "uncertain";
  return "fail";
}

const TONE_TEXT: Record<"pass" | "uncertain" | "fail", string> = {
  pass: "text-verdict-pass",
  uncertain: "text-verdict-uncertain",
  fail: "text-verdict-fail",
};

/**
 * Evaluator-quality report card (UC1 §2.4). Shows Cohen's kappa + per-label recall.
 * Designed for the /reliability unified view alongside DriftPanel.
 */
export function EvaluatorQualityPanel({ report }: { report: EvaluatorQuality }) {
  const tone = bandTone(report.agreement_band);
  const labels = Object.entries(report.per_label_recall);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-muted-foreground" aria-hidden />
          Evaluator quality
          <span className="text-xs font-normal text-muted-foreground">(judge vs human)</span>
        </CardTitle>
        <Badge variant={tone} className="uppercase tracking-wide">
          {report.agreement_band}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-stretch gap-4">
          <div className="flex flex-1 flex-col justify-center rounded-lg border border-hairline bg-surface/40 px-5 py-4">
            <div className={cn("font-mono text-4xl font-semibold tabular-nums tracking-tight", TONE_TEXT[tone])}>
              {report.cohen_kappa.toFixed(2)}
            </div>
            <div className="mt-1 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
              Cohen&apos;s kappa
            </div>
          </div>
          <div className="flex flex-1 flex-col justify-center rounded-lg border border-hairline bg-surface/40 px-5 py-4">
            <div className="font-mono text-4xl font-semibold tabular-nums tracking-tight text-foreground">
              {pct(report.accuracy)}
            </div>
            <div className="mt-1 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
              Raw agreement · {report.n_agreements}/{report.n_cases}
            </div>
          </div>
        </div>

        <div>
          <div className="mb-2 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
            Agreement by gold verdict
          </div>
          <div className="space-y-2">
            {labels.map(([label, recall]) => (
              <div key={label} className="flex items-center gap-3 text-sm">
                <span className="w-24 shrink-0 capitalize text-muted-foreground">{label}</span>
                <ConfidenceBar value={recall} className="flex-1" showLabel={false} />
                <span className="w-12 shrink-0 text-right font-mono tabular-nums text-foreground">
                  {pct(recall)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-sm leading-relaxed text-muted-foreground">{report.summary}</p>
      </CardContent>
    </Card>
  );
}
