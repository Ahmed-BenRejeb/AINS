import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  CircleDot,
  Loader2,
  Ban,
  type LucideIcon,
} from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type VerdictLike = "pass" | "fail" | "uncertain";
type RunStatusLike = "running" | "completed" | "failed" | "aborted";

interface VerdictConfig {
  label: string;
  variant: BadgeProps["variant"];
  Icon: LucideIcon;
}

const VERDICT_CONFIG: Record<VerdictLike, VerdictConfig> = {
  pass: { label: "PASS", variant: "pass", Icon: CheckCircle2 },
  fail: { label: "FAIL", variant: "fail", Icon: XCircle },
  uncertain: { label: "UNCERTAIN", variant: "uncertain", Icon: HelpCircle },
};

const STATUS_CONFIG: Record<RunStatusLike, VerdictConfig> = {
  completed: { label: "completed", variant: "neutral", Icon: CircleDot },
  running: { label: "running", variant: "uncertain", Icon: Loader2 },
  failed: { label: "failed", variant: "fail", Icon: XCircle },
  aborted: { label: "aborted", variant: "neutral", Icon: Ban },
};

export interface RunStatusBadgeProps {
  /** A verdict label (pass/fail/uncertain) or a run status (completed/...). */
  value: string;
  /** "verdict" renders the bold colour-coded verdict; "status" the run lifecycle. */
  kind?: "verdict" | "status";
  className?: string;
}

/**
 * The single source of truth for verdict + status colour and iconography.
 * PASS = emerald, FAIL = red, UNCERTAIN = amber — always paired with an icon so
 * the state is unmistakable even without colour.
 */
export function RunStatusBadge({ value, kind = "verdict", className }: RunStatusBadgeProps) {
  const config =
    kind === "verdict"
      ? (VERDICT_CONFIG[value as VerdictLike] ?? VERDICT_CONFIG.uncertain)
      : (STATUS_CONFIG[value as RunStatusLike] ?? STATUS_CONFIG.completed);
  const { label, variant, Icon } = config;
  return (
    <Badge variant={variant} className={cn("uppercase tracking-wide", className)}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {label}
    </Badge>
  );
}
