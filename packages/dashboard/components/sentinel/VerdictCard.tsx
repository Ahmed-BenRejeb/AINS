"use client";

import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  ScanSearch,
  AlertTriangle,
  PlayCircle,
  ArrowRight,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { DimensionTable } from "./DimensionTable";
import { AttributionBox } from "./AttributionBox";
import { ConfidenceBar } from "./ConfidenceBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import type { EvalVerdict, VerdictLabel } from "@/lib/types";
import { cn, pct, withMock } from "@/lib/utils";

interface VerdictTheme {
  label: string;
  Icon: LucideIcon;
  text: string;
  ring: string;
  glow: string;
}

const THEME: Record<VerdictLabel, VerdictTheme> = {
  pass: {
    label: "PASS",
    Icon: CheckCircle2,
    text: "text-verdict-pass",
    ring: "border-verdict-pass/40 bg-verdict-pass/[0.07]",
    glow: "shadow-[0_0_40px_-12px_rgba(16,185,129,0.5)]",
  },
  fail: {
    label: "FAIL",
    Icon: XCircle,
    text: "text-verdict-fail",
    ring: "border-verdict-fail/40 bg-verdict-fail/[0.07]",
    glow: "shadow-[0_0_40px_-12px_rgba(239,68,68,0.5)]",
  },
  uncertain: {
    label: "UNCERTAIN",
    Icon: HelpCircle,
    text: "text-verdict-uncertain",
    ring: "border-verdict-uncertain/40 bg-verdict-uncertain/[0.07]",
    glow: "shadow-[0_0_40px_-12px_rgba(245,158,11,0.5)]",
  },
};

/** Spring scale-in for every verdict; FAIL adds a brief red shake. */
function VerdictHero({ verdict }: { verdict: VerdictLabel }) {
  const theme = THEME[verdict];
  const shake =
    verdict === "fail"
      ? { x: [0, -8, 8, -6, 6, -3, 3, 0] }
      : { x: 0 };
  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1, ...shake }}
      transition={{
        scale: { type: "spring", stiffness: 320, damping: 18 },
        opacity: { duration: 0.25 },
        x: { duration: 0.5, ease: "easeInOut" },
      }}
      className={cn(
        "flex items-center gap-4 rounded-xl border px-6 py-5",
        theme.ring,
        theme.glow,
        verdict === "pass" && "animate-pulse-ring",
      )}
    >
      <theme.Icon className={cn("h-10 w-10", theme.text)} aria-hidden />
      <div>
        <div className={cn("font-mono text-3xl font-bold tracking-tight", theme.text)}>
          {theme.label}
        </div>
        <div className="text-xs uppercase tracking-wider text-muted-foreground">
          Overall verdict
        </div>
      </div>
    </motion.div>
  );
}

/**
 * Full verdict display: the hero badge, the recommended action, per-dimension
 * scores, failure attribution (on fail), the judge's self-evaluation, a
 * flag-for-human banner, and a replay link. Designed so a non-technical reader
 * understands the outcome without explanation.
 */
export function VerdictCard({
  verdict,
  mock = false,
}: {
  verdict: EvalVerdict;
  mock?: boolean;
}) {
  const label = (["pass", "fail", "uncertain"].includes(verdict.verdict)
    ? verdict.verdict
    : "uncertain") as VerdictLabel;
  const flagged = verdict.self_evaluation?.flag_for_human;

  return (
    <div className="space-y-6">
      {/* Hero + recommended action */}
      <div className="flex flex-col gap-4 md:flex-row md:items-stretch">
        <VerdictHero verdict={label} />
        <div className="flex flex-1 flex-col justify-center rounded-xl border border-hairline bg-card px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Recommended action
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground">
            {verdict.recommended_action || "-"}
          </p>
        </div>
      </div>

      {flagged && (
        <div className="flex items-start gap-3 rounded-lg border border-verdict-uncertain/40 bg-verdict-uncertain/[0.08] px-4 py-3 text-verdict-uncertain">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div className="text-sm">
            <span className="font-semibold">Flagged for human review.</span>{" "}
            <span className="text-verdict-uncertain/90">
              The judge is not confident enough to act autonomously on this verdict.
            </span>
          </div>
        </div>
      )}

      {/* Per-dimension scores */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Rubric dimensions</CardTitle>
        </CardHeader>
        <CardContent>
          <DimensionTable dimensions={verdict.dimensions} />
        </CardContent>
      </Card>

      {/* Failure attribution (only when something broke) */}
      {verdict.failure_attribution && (
        <AttributionBox attribution={verdict.failure_attribution} />
      )}

      {/* Self-evaluation */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <ScanSearch className="h-4 w-4 text-muted-foreground" aria-hidden />
            Judge self-evaluation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Judge confidence
            </span>
            <ConfidenceBar value={verdict.self_evaluation?.judge_confidence ?? 0} className="w-48" />
            <span className="font-mono text-sm tabular-nums text-foreground">
              {pct(verdict.self_evaluation?.judge_confidence)}
            </span>
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {verdict.self_evaluation?.self_critique || "-"}
          </p>
        </CardContent>
      </Card>

      {/* Replay link */}
      <div className="flex flex-wrap items-center gap-3">
        {verdict.replay_link && (
          <a
            href={verdict.replay_link}
            target="_blank"
            rel="noreferrer"
            className={cn(buttonVariants({ variant: "emerald" }))}
          >
            <PlayCircle className="h-4 w-4" aria-hidden />
            Open recorded replay
          </a>
        )}
        <Link
          href={withMock(`/replay/${verdict.run_id}`, mock)}
          className={cn(buttonVariants({ variant: "secondary" }))}
        >
          Replay in dashboard
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>
    </div>
  );
}
