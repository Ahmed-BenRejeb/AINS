import * as React from "react";
import { cn } from "@/lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Fill ratio in [0, 1]. */
  value: number;
  /** Tailwind class for the fill colour (e.g. "bg-verdict-pass"). */
  indicatorClassName?: string;
}

/** Slim inline progress bar used for confidence / score percentages. */
const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, indicatorClassName, ...props }, ref) => {
    const clamped = Math.max(0, Math.min(1, value));
    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuenow={Math.round(clamped * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        className={cn(
          "h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]",
          className,
        )}
        {...props}
      >
        <div
          className={cn("h-full rounded-full bg-foreground transition-all", indicatorClassName)}
          style={{ width: `${clamped * 100}%` }}
        />
      </div>
    );
  },
);
Progress.displayName = "Progress";

export { Progress };
