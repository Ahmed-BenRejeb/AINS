import { Progress } from "@/components/ui/progress";
import { cn, pct } from "@/lib/utils";

/**
 * Inline score/confidence indicator: a right-aligned monospace percentage above a
 * slim progress bar. Colour ramps red → amber → emerald with the value.
 */
export function ConfidenceBar({
  value,
  className,
  showLabel = true,
}: {
  value: number;
  className?: string;
  showLabel?: boolean;
}) {
  const indicator =
    value >= 0.75
      ? "bg-verdict-pass"
      : value >= 0.5
        ? "bg-verdict-uncertain"
        : "bg-verdict-fail";
  return (
    <div className={cn("min-w-[64px]", className)}>
      {showLabel && (
        <div className="mb-1 text-right font-mono text-xs tabular-nums text-foreground">
          {pct(value)}
        </div>
      )}
      <Progress value={value} indicatorClassName={indicator} />
    </div>
  );
}
