"use client";

import Link from "next/link";
import { AlertTriangle, Flag, Inbox, ArrowUpRight } from "lucide-react";
import { PageTransition, motion, staggerContainer, staggerItem } from "../motion";
import { StatsRow } from "../StatsRow";
import { RunStatusBadge } from "../RunStatusBadge";
import { DataSourceBadge } from "../DataSourceBadge";
import { EmptyState } from "../EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { DataSource, OverviewStats, VerdictSummary } from "@/lib/types";
import { timeAgo, truncateId, withMock } from "@/lib/utils";

const PIPELINE = [
  { tag: "UC2", name: "Flight Recorder", desc: "records every LLM + tool call" },
  { tag: "UC1", name: "Eval Engine", desc: "judges traces → auditable verdicts" },
  { tag: "UC3", name: "Atlassian Agent", desc: "verdicts land as Jira incidents" },
];

export function HomeView({
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
  const flagged = summaries.filter((v) => v.flag_for_human);

  return (
    <PageTransition className="space-y-8">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-xl border border-hairline bg-card">
        <div className="absolute inset-0 bg-grid opacity-60" aria-hidden />
        <div className="relative flex flex-col gap-5 p-6 md:p-8">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
                Sentinel — AI Agent Reliability Platform
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                Record, judge, and replay AI agent runs. Auditable verdicts with failure
                attribution — dogfooded on a real Atlassian Rovo agent.
              </p>
            </div>
            <DataSourceBadge source={source} title={sourceError} />
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {PIPELINE.map((p) => (
              <div
                key={p.tag}
                className="rounded-lg border border-hairline bg-canvas/60 px-3 py-2.5"
              >
                <div className="flex items-center gap-2">
                  <span className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {p.tag}
                  </span>
                  <span className="text-sm font-medium text-foreground">{p.name}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Flag alert banner */}
      {flagged.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 rounded-lg border border-verdict-fail/40 bg-verdict-fail/[0.08] px-4 py-3 text-verdict-fail"
        >
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
          <span className="text-sm">
            <span className="font-semibold">
              {flagged.length} verdict{flagged.length > 1 ? "s" : ""} flagged for human review.
            </span>{" "}
            <span className="text-verdict-fail/90">
              The judge was not confident enough to act autonomously.
            </span>
          </span>
        </motion.div>
      )}

      {/* Stats */}
      <StatsRow stats={stats} />

      {/* Recent verdicts */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>Recent verdicts</CardTitle>
          <Link
            href={withMock("/runs", mock)}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            View all runs
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </CardHeader>
        <CardContent className="pt-0">
          {recent.length === 0 ? (
            <EmptyState
              Icon={Inbox}
              title="No verdicts yet"
              description="Once the eval engine judges a run, its verdict appears here."
            />
          ) : (
            <motion.div variants={staggerContainer} initial="hidden" animate="show">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[160px]">Run</TableHead>
                    <TableHead>Verdict</TableHead>
                    <TableHead className="w-[120px]">Flag</TableHead>
                    <TableHead className="w-[140px] text-right">When</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recent.map((v) => (
                    <motion.tr
                      key={v.run_id}
                      variants={staggerItem}
                      className="group cursor-pointer border-b border-hairline transition-colors hover:bg-white/[0.025]"
                    >
                      <TableCell className="p-0">
                        <Link
                          href={withMock(`/verdicts/${v.run_id}`, mock)}
                          className="block px-4 py-3 font-mono text-sm text-foreground"
                        >
                          {truncateId(v.run_id)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Link href={withMock(`/verdicts/${v.run_id}`, mock)} className="block">
                          <RunStatusBadge value={v.verdict} kind="verdict" />
                        </Link>
                      </TableCell>
                      <TableCell>
                        {v.flag_for_human ? (
                          <span className="inline-flex items-center gap-1.5 text-xs text-verdict-uncertain">
                            <Flag className="h-3.5 w-3.5" aria-hidden />
                            review
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                        {timeAgo(v.timestamp)}
                      </TableCell>
                    </motion.tr>
                  ))}
                </TableBody>
              </Table>
            </motion.div>
          )}
        </CardContent>
      </Card>
    </PageTransition>
  );
}
