import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-hairline bg-muted text-muted-foreground",
        outline: "border-hairline text-foreground",
        pass: "border-verdict-pass/30 bg-verdict-pass/10 text-verdict-pass",
        fail: "border-verdict-fail/30 bg-verdict-fail/10 text-verdict-fail",
        uncertain: "border-verdict-uncertain/30 bg-verdict-uncertain/10 text-verdict-uncertain",
        neutral: "border-hairline bg-white/[0.03] text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

/** Small status pill. Use the verdict variants for PASS/FAIL/UNCERTAIN. */
function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
