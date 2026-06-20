"use client";

import { Activity, CheckCircle2, Target, Flag, type LucideIcon } from "lucide-react";
import { AnimatedCounter } from "./AnimatedCounter";
import { HoverCard } from "./motion";
import { Card } from "@/components/ui/card";
import type { OverviewStats } from "@/lib/types";
import { cn } from "@/lib/utils";

interface StatDef {
  label: string;
  Icon: LucideIcon;
  value: number;
  decimals: number;
  suffix: string;
  hint: string;
  accent: string;
}

/**
 * Home-page metric row: Total Runs, Pass Rate, pass^k (last 8), Flagged for Human.
 * Each value counts up on load. pass^k is binary by design (all() semantics) — it
 * is 1.00 only when every trial in the window passed.
 */
export function StatsRow({ stats }: { stats: OverviewStats }) {
  const defs: StatDef[] = [
    {
      label: "Total Runs",
      Icon: Activity,
      value: stats.total_runs,
      decimals: 0,
      suffix: "",
      hint: "recorded by the flight recorder",
      accent: "text-foreground",
    },
    {
      label: "Pass Rate",
      Icon: CheckCircle2,
      value: Math.round(stats.pass_rate * 100),
      decimals: 0,
      suffix: "%",
      hint: "verdicts judged pass",
      accent: stats.pass_rate >= 0.7 ? "text-verdict-pass" : "text-verdict-uncertain",
    },
    {
      label: "pass^k (last 8)",
      Icon: Target,
      value: stats.pass_hat_k,
      decimals: 2,
      suffix: "",
      hint: "1.00 only if all 8 trials pass",
      accent: stats.pass_hat_k >= 1 ? "text-verdict-pass" : "text-verdict-fail",
    },
    {
      label: "Flagged for Human",
      Icon: Flag,
      value: stats.flagged_for_human,
      decimals: 0,
      suffix: "",
      hint: "verdicts needing review",
      accent: stats.flagged_for_human > 0 ? "text-verdict-uncertain" : "text-foreground",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {defs.map((def, i) => (
        <HoverCard key={def.label} delay={i * 0.06}>
          <Card className="h-full p-5">
            <div className="flex items-start justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {def.label}
              </span>
              <def.Icon className={cn("h-4 w-4", def.accent)} aria-hidden />
            </div>
            <div className={cn("mt-3 font-mono text-4xl font-semibold tabular-nums", def.accent)}>
              <AnimatedCounter value={def.value} decimals={def.decimals} suffix={def.suffix} />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{def.hint}</p>
          </Card>
        </HoverCard>
      ))}
    </div>
  );
}
