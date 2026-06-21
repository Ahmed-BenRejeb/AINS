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
import { Tilt } from "../motion";
import { ReliabilityRing } from "../ReliabilityRing";
import { AnimatedCounter } from "../AnimatedCounter";
import { DataSourceBadge } from "../DataSourceBadge";
import { EmptyState } from "../EmptyState";
import { SentinelEmblem, SentinelLockup } from "../Logo";
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
    n: "01",
    name: "Record",
    Icon: Radio,
    body: "Every LLM and tool call is taped into a hash-chained, signed trace.",
    foot: "Flight Recorder",
  },
  {
    n: "02",
    name: "Judge",
    Icon: Gavel,
    body: "A calibrated judge scores each run and attributes the failing step.",
    foot: "Eval Engine",
  },
  {
    n: "03",
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
  const liveLabel = source === "live" ? "RECORDING" : source === "mock" ? "DEMO" : "RECORDING";

  return (
    <div className="relative">
      {/* ───────────────────────── Hero ───────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="aurora animate-aurora pointer-events-none absolute inset-0 -z-10" aria-hidden />
        <div className="hexmesh pointer-events-none absolute inset-0 -z-10" aria-hidden />
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-48 bg-gradient-to-b from-transparent to-canvas"
          aria-hidden
        />

        <div className="mx-auto grid min-h-[calc(100dvh-4rem)] w-full max-w-[1180px] grid-cols-1 items-center gap-12 px-5 pb-20 pt-14 md:px-8 lg:grid-cols-12 lg:gap-8 lg:pt-16">
          {/* Left: message. Content is visible by default; the fade-up is a paint-time
              CSS enhancement (never gates visibility on JS / scroll). */}
          <div className="lg:col-span-7">
            <div
              className="flex items-center gap-2.5 motion-safe:animate-fade-up"
              style={{ animationDelay: "0ms" }}
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent/70" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              <span className="font-mono text-xs uppercase tracking-[0.25em] text-accent">
                {liveLabel}
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                / {stats.total_runs} runs taped
              </span>
            </div>

            <h1
              className="mt-6 max-w-[16ch] font-display text-[2.9rem] font-bold leading-[0.98] tracking-[-0.035em] text-foreground motion-safe:animate-fade-up sm:text-6xl lg:text-[4.6rem]"
              style={{ animationDelay: "60ms" }}
            >
              The flight recorder for AI agents.
            </h1>

            <p
              className="mt-6 max-w-[40ch] text-[15px] leading-relaxed text-muted-foreground motion-safe:animate-fade-up sm:text-base"
              style={{ animationDelay: "120ms" }}
            >
              Record every LLM and tool call, judge each run with calibrated verdicts, and replay it
              byte for byte. Reliability infrastructure for the Atlassian ecosystem.
            </p>

            <div
              className="mt-9 flex flex-wrap items-center gap-3 motion-safe:animate-fade-up"
              style={{ animationDelay: "180ms" }}
            >
              <Link
                href={verdictHref}
                className="group inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink shadow-accent-glow transition-transform duration-150 ease-out hover:bg-[#43efba] active:scale-[0.98]"
              >
                Inspect a verdict
                <ArrowRight className="h-4 w-4 transition-transform duration-200 ease-out group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#loop"
                className="inline-flex items-center gap-2 rounded-lg border border-hairline-strong bg-surface/60 px-5 py-2.5 text-sm font-medium text-foreground transition-colors duration-200 ease-out hover:border-accent/40 active:scale-[0.98]"
              >
                How it works
              </a>
            </div>
          </div>

          {/* Right: brand emblem + instrument telemetry (real data, bezel frame) */}
          <div
            className="lg:col-span-5 motion-safe:animate-fade-up"
            style={{ animationDelay: "220ms" }}
          >
            <Tilt className="mx-auto w-full max-w-sm">
              <div className="flex flex-col items-center">
                <SentinelEmblem className="h-36 w-36 text-foreground" />
                <div className="bezel mt-6 w-full rounded-xl border border-hairline-strong bg-surface/90 p-5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                      Fleet telemetry
                    </span>
                    <DataSourceBadge source={source} title={sourceError} />
                  </div>

                  <div className="mt-5 flex items-center gap-5">
                    <ReliabilityRing value={stats.pass_rate} size={132} label="Pass rate" />
                    <div className="flex-1 space-y-3">
                      <Readout label="Runs" value={stats.total_runs} />
                      <Readout
                        label="pass^k"
                        value={stats.pass_hat_k}
                        decimals={2}
                        accent={stats.pass_hat_k >= 1 ? "text-verdict-pass" : "text-verdict-fail"}
                      />
                      <Readout
                        label="Flagged"
                        value={stats.flagged_for_human}
                        accent={stats.flagged_for_human > 0 ? "text-verdict-uncertain" : undefined}
                      />
                    </div>
                  </div>

                  <div className="mt-5 space-y-1.5 border-t border-hairline pt-4">
                    {previewVerdicts.length === 0 ? (
                      <p className="py-3 text-center text-xs text-muted-foreground">No verdicts yet.</p>
                    ) : (
                      previewVerdicts.map((v) => {
                        const g = VERDICT_GLYPH[v.verdict];
                        return (
                          <div key={v.run_id} className="flex items-center gap-2.5 py-1">
                            <g.Icon className={cn("h-4 w-4 shrink-0", g.cls)} aria-hidden />
                            <span className="font-mono text-xs text-foreground">
                              {truncateId(v.run_id)}
                            </span>
                            <span className={cn("ml-auto font-mono text-[11px]", g.cls)}>{g.label}</span>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            </Tilt>
          </div>
        </div>
      </section>

      {/* ───────────────────── Stat band (amplified) ───────────────────── */}
      <section className="border-y border-hairline bg-canvas-2/50">
        <div className="mx-auto grid w-full max-w-[1180px] grid-cols-2 divide-hairline px-5 md:grid-cols-4 md:divide-x md:px-8">
          <BandStat label="Runs recorded" value={stats.total_runs} />
          <BandStat label="Pass rate" value={Math.round(stats.pass_rate * 100)} suffix="%" accent />
          <BandStat label="pass^k · last 8" value={stats.pass_hat_k} decimals={2} />
          <BandStat label="Flagged for human" value={stats.flagged_for_human} />
        </div>
      </section>

      {/* ───────────────────── The loop ───────────────────── */}
      <section id="loop" className="mx-auto w-full max-w-[1180px] px-5 py-28 md:px-8">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <h2 className="font-display text-4xl font-bold tracking-[-0.025em] sm:text-5xl">
              One loop,
              <br />
              three jobs.
            </h2>
            <p className="mt-5 max-w-sm text-[15px] leading-relaxed text-muted-foreground">
              We built the reliability infrastructure a Marketplace AI vendor needs, then dogfooded
              it on a real Atlassian agent.
            </p>
          </div>

          <ol className="relative lg:col-span-8">
            <span
              className="pointer-events-none absolute left-[27px] top-6 bottom-6 w-px bg-gradient-to-b from-accent/50 via-hairline-strong to-transparent"
              aria-hidden
            />
            {LOOP.map((stage, i) => (
              <li
                key={stage.n}
                className="relative flex gap-6 pb-10 last:pb-0 motion-safe:animate-fade-up"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <span className="relative z-10 flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-hairline-strong bg-surface text-accent">
                  <stage.Icon className="h-6 w-6" aria-hidden />
                </span>
                <div className="pt-1">
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono text-xs text-accent">{stage.n}</span>
                    <h3 className="font-display text-2xl font-semibold tracking-tight">{stage.name}</h3>
                    <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                      {stage.foot}
                    </span>
                  </div>
                  <p className="mt-2 max-w-md text-[15px] leading-relaxed text-muted-foreground">
                    {stage.body}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ───────────────────── Recent verdicts ───────────────────── */}
      <section className="mx-auto w-full max-w-[1180px] px-5 pb-28 md:px-8">
        <div className="mb-6 flex items-end justify-between">
          <h2 className="font-display text-3xl font-bold tracking-[-0.02em]">Recent verdicts</h2>
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
          <div className="overflow-hidden rounded-xl border border-hairline">
            {recent.map((v, i) => {
              const g = VERDICT_GLYPH[v.verdict];
              return (
                <div
                  key={v.run_id}
                  className="motion-safe:animate-fade-up"
                  style={{ animationDelay: `${i * 55}ms` }}
                >
                  <Link
                    href={withMock(`/verdicts/${v.run_id}`, mock)}
                    className="group flex items-center gap-4 border-b border-hairline px-5 py-4 transition-colors duration-200 ease-out last:border-0 hover:bg-accent/[0.04]"
                  >
                    <g.Icon className={cn("h-5 w-5 shrink-0", g.cls)} aria-hidden />
                    <span className={cn("w-24 font-mono text-xs font-medium", g.cls)}>{g.label}</span>
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
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ───────────────────── Footer ───────────────────── */}
      <footer className="border-t border-hairline">
        <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-4 px-5 py-12 md:flex-row md:items-center md:justify-between md:px-8">
          <div>
            <SentinelLockup />
            <div className="mt-2 font-mono text-xs text-muted-foreground">
              {pct(stats.pass_rate)} pass rate across {stats.total_runs} recorded runs
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

function Readout({
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
    <div className="flex items-baseline justify-between gap-3 border-b border-hairline/60 pb-2 last:border-0 last:pb-0">
      <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={cn("font-mono text-base font-semibold tabular-nums text-foreground", accent)}>
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
  accent = false,
}: {
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  accent?: boolean;
}) {
  return (
    <div className="px-1 py-10 md:px-7">
      <div
        className={cn(
          "font-mono text-5xl font-semibold tabular-nums tracking-tight sm:text-6xl",
          accent ? "text-accent" : "text-foreground",
        )}
      >
        <AnimatedCounter value={value} decimals={decimals} suffix={suffix} />
      </div>
      <div className="mt-2 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
    </div>
  );
}
