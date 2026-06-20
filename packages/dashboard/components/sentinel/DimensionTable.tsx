import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfidenceBar } from "./ConfidenceBar";
import type { DimensionScore } from "@/lib/types";
import { cn, pct } from "@/lib/utils";

// Canonical dimension order (mirrors eval-engine JUDGE_DIMENSIONS).
const DIMENSION_ORDER = ["correctness", "efficiency", "safety", "reasoning_quality"];

function prettyName(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "text-verdict-pass";
  if (score >= 0.45) return "text-verdict-uncertain";
  return "text-verdict-fail";
}

/**
 * Per-dimension rubric scores: name, the judge's reason, numeric score (right-
 * aligned monospace), and an inline confidence bar. The four standard dimensions
 * sort to the front; any extras follow.
 */
export function DimensionTable({
  dimensions,
}: {
  dimensions: Record<string, DimensionScore>;
}) {
  const keys = Object.keys(dimensions).sort((a, b) => {
    const ia = DIMENSION_ORDER.indexOf(a);
    const ib = DIMENSION_ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[150px]">Dimension</TableHead>
          <TableHead>Reasoning</TableHead>
          <TableHead className="w-[88px] text-right">Score</TableHead>
          <TableHead className="w-[120px] text-right">Confidence</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {keys.map((key) => {
          const dim = dimensions[key];
          return (
            <TableRow key={key} className="align-top hover:bg-transparent">
              <TableCell className="font-medium text-foreground">{prettyName(key)}</TableCell>
              <TableCell className="max-w-md text-sm leading-relaxed text-muted-foreground">
                {dim.reason}
              </TableCell>
              <TableCell className="text-right">
                <span className={cn("font-mono text-base tabular-nums", scoreColor(dim.score))}>
                  {dim.score.toFixed(2)}
                </span>
              </TableCell>
              <TableCell>
                <div className="flex flex-col items-end gap-1">
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    {pct(dim.confidence)}
                  </span>
                  <ConfidenceBar value={dim.confidence} showLabel={false} className="w-20" />
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
