"use client";

import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Radio,
  Gavel,
  Workflow,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Inbox,
  Flag,
  type LucideIcon,
} from "lucide-react";
import { motion, Tilt, staggerContainer, staggerItem, EASE_OUT } from "../motion";
import { ReliabilityRing } from "../ReliabilityRing";
import { AnimatedCounter } from "../AnimatedCounter";
import { DataSourceBadge } from "../DataSourceBadge";
import { EmptyState } from "../EmptyState";
import { LANGFUSE_URL } from "@/lib/api";
import type { DataSource, OverviewStats, VerdictLabel, VerdictSummary } from "@/lib/types";
import { cn, pct, timeAgo, truncateId, withMock } from "@/lib/utils";

const VERDICT_GLYPH: Record<VerdictLabel, { Icon: LucideIcon; cls: string; label: string }> = {
  pass: { Icon: CheckCircle2, cls: "text-verdict-pass", label: "PASS" },
  fail: { Icon: XCircle, cls: "text-verdict-fail", label: "FAIL" },
  uncertain: { Icon: HelpCircle, cls: "text-verdict-uncertain", label: "UNCERTAIN" },
};

const LOOP = [
  {
    tag: "UC2",
    name: "Record",
    Icon: Radio,
    body: "Every LLM and tool call is taped into a hash-chained, signed trace.",
    foot: "Flight Recorder",
  },
  {
    tag: "UC1",
    name: "Judge",
    Icon: Gavel,
    body: "A calibrated judge scores each run and attributes the failing step.",
    foot: "Eval Engine",
  },
  {
    tag: "UC3",
    name: "Act",
    Icon: Workflow,
    body: "Verdicts land as Jira incidents on a real Atlassian Rovo agent.",
    foot: "Atlassian Agent",
  },
];

export function HomeLanding({
  stats,
  summaries,
  source,
  sourceError,
  mock,
}: {
  stats: OverviewStats;
  summaries: VerdictSummary[];
  source: DataSource;
  sourceError?: string;
  mock: boolean;
}) {
  const recent = summaries.slice(0, 5);
  const previewVerdicts = summaries.slice(0, 3);
  const firstRunId = summaries[0]?.run_id ?? "";
  const verdictHref = firstRunId
    ? withMock(`/verdicts/${firstRunId}`, mock)
    : withMock("/runs", mock);
  const liveLabel =
    source === "live" ? "Live · recording" : source === "mock" ? "Demo data" : "Live · fallback";

  return (
    <div className="relative">
      {/* ───────────────────────── Hero ───────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="aurora animate-aurora pointer-events-none absolute inset-0 -z-10" aria-hidden />
        <div className="dotgrid pointer-events-none absolute inset-0 -z-10 opacity-40" aria-hidden />
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-b from-transparent to-canvas"
          aria-hidden
        />

        <div className="mx-auto grid min-h-[calc(100dvh-4rem)] w-full max-w-[1180px] grid-cols-1 items-center gap-12 px-5 pb-20 pt-16 md:px-8 lg:grid-cols-12 lg:pt-20">
          {/* Left: message */}
          <motion.div
            initial="hidden"
            animate="show"
            variants={staggerContainer}
            className="lg:col-span-6"
          >
            <motion.div variants={staggerItem}>
              <span className="inline-flex items-center gap-2 rounded-full border border-hairline-strong bg-surface/60 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                </span>
                {liveLabel}
              </span>
            </motion.div>

            <motion.h1
              variants={staggerItem}
              className="mt-6 max-w-[18ch] text-[2.6rem] font-semibold leading-[1.05] tracking-[-0.03em] text-foreground sm:text-5xl lg:text-[3.55rem]"
            >
              The reliability layer for AI agents.
            </motion.h1>

            <motion.p
              variants={staggerItem}
              className="mt-5 max-w-[34rem] text-[15px] leading-relaxed text-muted-foreground sm:text-base"
            >
              Sentinel records every LLM and tool call, judges each run with calibrated verdicts, and
              replays it byte for byte. Built for the Atlassian ecosystem.
            </motion.p>

            <motion.div variants={staggerItem} className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href={verdictHref}
                className="group inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-accent-ink shadow-accent-glow transition-transform duration-150 ease-out hover:bg-[#43efba] active:scale-[0.98]"
              >
                Inspect a verdict
                <ArrowRight className="h-4 w-4 transition-transform duration-200 ease-out group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#loop"
                className="inline-flex items-center gap-2 rounded-lg border border-hairline-strong bg-surface/50 px-5 py-2.5 text-sm font-medium text-foreground transition-colors duration-200 ease-out hover:border-accent/40 active:scale-[0.98]"
              >
                How it works
              </a>
            </motion.div>
          </motion.div>

          {/* Right: real component preview (not a mock screenshot) */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: EASE_OUT }}
            className="lg:col-span-6"
          >
            <Tilt className="mx-auto w-full max-w-md">
              <div className="rounded-xl border border-hairline-strong bg-surface/80 p-5 shadow-elevated backdrop-blur-sm [transform:translateZ(40px)]">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Fleet reliability
                  </span>
                  <DataSourceBadge source={source} title={sourceError} />
                </div>

                <div className="mt-5 flex items-center gap-6">
                  <ReliabilityRing value={stats.pass_rate} size={150} />
                  <div className="flex-1 space-y-3">
                    <PreviewStat label="Runs recorded" value={stats.total_runs} />
                    <PreviewStat
                      label="pass^k · last 8"
                      value={stats.pass_hat_k}
                      decimals={2}
                      accent={stats.pass_hat_k >= 1 ? "text-verdict-pass" : "text-verdict-fail"}
                    />
                    <PreviewStat
                      label="Flagged"
                      value={stats.flagged_for_human}
                      accent={stats.flagged_for_human > 0 ? "text-verdict-uncertain" : undefined}
                    />
                  </div>
                </div>

                <div className="mt-5 space-y-1.5 border-t border-hairline pt-4">
                  {previewVerdicts.length === 0 ? (
                    <p className="py-3 text-center text-xs text-muted-foreground">
                      No verdicts yet.
                    </p>
                  ) : (
                    previewVerdicts.map((v) => {
                      const g = VERDICT_GLYPH[v.verdict];
                      return (
                        <div key={v.run_id} className="flex items-center gap-2.5 py-1">
                          <g.Icon className={cn("h-4 w-4 shrink-0", g.cls)} aria-hidden />
                          <span className="font-mono text-xs text-foreground">
                            {truncateId(v.run_id)}
                          </span>
                          <span className={cn("ml-auto font-mono text-[11px]", g.cls)}>
                            {g.label}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </Tilt>
          </motion.div>
        </div>
      </section>

      {/* ───────────────────── Stat band ───────────────────── */}
      <section className="border-y border-hairline bg-canvas-2/40">
        <div className="mx-auto grid w-full max-w-[1180px] grid-cols-2 divide-hairline px-5 md:grid-cols-4 md:divide-x md:px-8">
          <BandStat label="Total runs" value={stats.total_runs} />
          <BandStat label="Pass rate" value={Math.round(stats.pass_rate * 100)} suffix="%" />
          <BandStat label="pass^k (last 8)" value={stats.pass_hat_k} decimals={2} />
          <BandStat label="Flagged for human" value={stats.flagged_for_human} />
        </div>
      </section>

      {/* ───────────────────── The loop ───────────────────── */}
      <section id="loop" className="mx-auto w-full max-w-[1180px] px-5 py-24 md:px-8">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <h2 className="text-3xl font-semibold tracking-[-0.02em] sm:text-4xl">
              One loop, three jobs.
            </h2>
            <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-muted-foreground">
              We built the reliability infrastructure a Marketplace AI vendor needs, then dogfooded
              it on a real Atlassian agent.
            </p>
          </div>

          <motion.ol
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="relative lg:col-span-8"
          >
            {/* through-line */}
            <span
              className="pointer-events-none absolute left-[19px] top-3 bottom-3 w-px bg-gradient-to-b from-accent/40 via-hairline-strong to-transparent"
              aria-hidden
            />
            {LOOP.map((stage) => (
              <motion.li
                key={stage.tag}
                variants={staggerItem}
                className="relative flex gap-5 pb-8 last:pb-0"
              >
                <span className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-hairline-strong bg-surface text-accent">
                  <stage.Icon className="h-5 w-5" aria-hidden />
                </span>
                <div className="pt-0.5">
                  <div className="flex items-baseline gap-2.5">
                    <h3 className="text-lg font-semibold tracking-tight">{stage.name}</h3>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {stage.tag} · {stage.foot}
                    </span>
                  </div>
                  <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
                    {stage.body}
                  </p>
                </div>
              </motion.li>
            ))}
          </motion.ol>
        </div>
      </section>

      {/* ───────────────────── Recent verdicts ───────────────────── */}
      <section className="mx-auto w-full max-w-[1180px] px-5 pb-24 md:px-8">
        <div className="mb-6 flex items-end justify-between">
          <h2 className="text-2xl font-semibold tracking-[-0.02em]">Recent verdicts</h2>
          <Link
            href={withMock("/runs", mock)}
            className="group inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors duration-200 ease-out hover:text-foreground"
          >
            View all runs
            <ArrowUpRight className="h-4 w-4 transition-transform duration-200 ease-out group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </div>

        {recent.length === 0 ? (
          <EmptyState
            Icon={Inbox}
            title="No verdicts yet"
            description="Once the eval engine judges a run, its verdict appears here."
          />
        ) : (
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="overflow-hidden rounded-xl border border-hairline"
          >
            {recent.map((v) => {
              const g = VERDICT_GLYPH[v.verdict];
              return (
                <motion.div key={v.run_id} variants={staggerItem}>
                  <Link
                    href={withMock(`/verdicts/${v.run_id}`, mock)}
                    className="group flex items-center gap-4 border-b border-hairline px-5 py-4 transition-colors duration-200 ease-out last:border-0 hover:bg-white/[0.02]"
                  >
                    <g.Icon className={cn("h-5 w-5 shrink-0", g.cls)} aria-hidden />
                    <span className={cn("w-24 font-mono text-xs font-medium", g.cls)}>
                      {g.label}
                    </span>
                    <span className="font-mono text-sm text-foreground">{truncateId(v.run_id)}</span>
                    {v.flag_for_human && (
                      <span className="inline-flex items-center gap-1 rounded-md border border-verdict-uncertain/30 bg-verdict-uncertain/10 px-1.5 py-0.5 text-[11px] text-verdict-uncertain">
                        <Flag className="h-3 w-3" aria-hidden />
                        review
                      </span>
                    )}
                    <span
                      suppressHydrationWarning
                      className="ml-auto font-mono text-xs tabular-nums text-muted-foreground"
                    >
                      {timeAgo(v.timestamp)}
                    </span>
                    <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 ease-out group-hover:translate-x-0.5 group-hover:text-foreground" />
                  </Link>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </section>

      {/* ───────────────────── Footer ───────────────────── */}
      <footer className="border-t border-hairline">
        <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-4 px-5 py-10 md:flex-row md:items-center md:justify-between md:px-8">
          <div>
            <div className="text-sm font-semibold tracking-tight">Sentinel</div>
            <div className="mt-1 text-xs text-muted-foreground">
              AI agent reliability platform · {pct(stats.pass_rate)} pass rate across{" "}
              {stats.total_runs} runs
            </div>
          </div>
          <div className="flex items-center gap-5 text-sm text-muted-foreground">
            <Link href={withMock("/runs", mock)} className="hover:text-foreground">
              Runs
            </Link>
            <a href={LANGFUSE_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
              Langfuse
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function PreviewStat({
  label,
  value,
  decimals = 0,
  accent,
}: {
  label: string;
  value: number;
  decimals?: number;
  accent?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn("font-mono text-sm font-medium tabular-nums text-foreground", accent)}>
        <AnimatedCounter value={value} decimals={decimals} />
      </span>
    </div>
  );
}

function BandStat({
  label,
  value,
  decimals = 0,
  suffix = "",
}: {
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
}) {
  return (
    <div className="px-1 py-8 md:px-6">
      <div className="font-mono text-3xl font-semibold tabular-nums text-foreground sm:text-4xl">
        <AnimatedCounter value={value} decimals={decimals} suffix={suffix} />
      </div>
      <div className="mt-1.5 text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
