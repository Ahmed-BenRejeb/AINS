"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { Inbox, ChevronRight } from "lucide-react";
import { PageTransition, motion, staggerContainer, staggerItem } from "../motion";
import { PageHeader } from "../PageHeader";
import { RunStatusBadge } from "../RunStatusBadge";
import { EmptyState } from "../EmptyState";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { DataSource, RunManifestRow } from "@/lib/types";
import { timeAgo, truncateId, withMock } from "@/lib/utils";

/**
 * All recorded runs as a clickable table (row → trace). Empty state nudges toward
 * `?mock=true`. Receives the server-fetched run list and its data-source.
 */
export function RunsView({
  runs,
  source,
  sourceError,
  mock,
}: {
  runs: RunManifestRow[];
  source: DataSource;
  sourceError?: string;
  mock: boolean;
}) {
  const router = useRouter();

  return (
    <PageTransition className="mx-auto w-full max-w-[1180px] space-y-6 px-5 py-10 md:px-8">
      <PageHeader
        title="Recorded runs"
        subtitle={`${runs.length} run${runs.length === 1 ? "" : "s"} captured by the flight recorder`}
        source={source}
        sourceError={sourceError}
      />

      {runs.length === 0 ? (
        <EmptyState
          Icon={Inbox}
          title="No runs recorded yet"
          description="Trigger an analysis on the Atlassian agent to record a run, or explore the demo with fixture data."
          action={
            <Link
              href="/runs?mock=true"
              className="text-sm text-verdict-pass underline-offset-4 hover:underline"
            >
              Load demo data (?mock=true)
            </Link>
          }
        />
      ) : (
        <Card className="overflow-hidden">
          <motion.div variants={staggerContainer} initial="hidden" animate="show">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[150px]">Run ID</TableHead>
                  <TableHead>Agent · Task</TableHead>
                  <TableHead className="w-[140px]">Status</TableHead>
                  <TableHead className="w-[90px] text-right">Steps</TableHead>
                  <TableHead className="w-[130px] text-right">Started</TableHead>
                  <TableHead className="w-[40px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const href = withMock(`/runs/${run.run_id}`, mock);
                  return (
                    <motion.tr
                      key={run.run_id}
                      variants={staggerItem}
                      onClick={() => router.push(href)}
                      className="group cursor-pointer border-b border-hairline transition-colors hover:bg-white/[0.025]"
                    >
                      <TableCell className="font-mono text-sm text-foreground">
                        {truncateId(run.run_id)}
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-xs text-muted-foreground">{run.agent_id}</div>
                        <div className="text-sm text-foreground">{run.task_id}</div>
                      </TableCell>
                      <TableCell>
                        <RunStatusBadge value={String(run.status)} kind="status" />
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm tabular-nums text-foreground">
                        {run.step_count}
                      </TableCell>
                      <TableCell
                        suppressHydrationWarning
                        className="text-right font-mono text-xs tabular-nums text-muted-foreground"
                      >
                        {timeAgo(run.started_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                      </TableCell>
                    </motion.tr>
                  );
                })}
              </TableBody>
            </Table>
          </motion.div>
        </Card>
      )}
    </PageTransition>
  );
}
