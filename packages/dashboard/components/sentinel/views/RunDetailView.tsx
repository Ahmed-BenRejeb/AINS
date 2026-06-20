"use client";

import Link from "next/link";
import { PlayCircle, Gavel, ListTree, FileWarning } from "lucide-react";
import { PageTransition } from "../motion";
import { PageHeader } from "../PageHeader";
import { RunStatusBadge } from "../RunStatusBadge";
import { StepTimeline } from "../StepTimeline";
import { EmptyState } from "../EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import type { DataSource, RunDetail } from "@/lib/types";
import { cn, formatTimestamp, truncateId, withMock } from "@/lib/utils";

function MetaItem({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-sm text-foreground", mono && "font-mono")}>{value}</div>
    </div>
  );
}

export function RunDetailView({
  detail,
  source,
  sourceError,
  mock,
}: {
  detail: RunDetail;
  source: DataSource;
  sourceError?: string;
  mock: boolean;
}) {
  const { manifest, trace, run_id } = detail;
  const stepCount = manifest?.step_count ?? trace.length;

  return (
    <PageTransition className="space-y-6">
      <PageHeader
        title="Execution trace"
        subtitle={
          <span className="font-mono">{run_id}</span>
        }
        source={source}
        sourceError={sourceError}
        backHref={withMock("/runs", mock)}
        backLabel="All runs"
        actions={
          <div className="flex items-center gap-2">
            <Link
              href={withMock(`/replay/${run_id}`, mock)}
              className={cn(buttonVariants({ variant: "emerald", size: "sm" }))}
            >
              <PlayCircle className="h-4 w-4" aria-hidden />
              Replay
            </Link>
            <Link
              href={withMock(`/verdicts/${run_id}`, mock)}
              className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
            >
              <Gavel className="h-4 w-4" aria-hidden />
              View verdict
            </Link>
          </div>
        }
      />

      {/* Manifest summary */}
      <Card>
        <CardContent className="grid grid-cols-2 gap-y-5 p-5 sm:grid-cols-3 lg:grid-cols-4">
          <MetaItem label="Run ID" value={truncateId(run_id, 12)} mono />
          <MetaItem label="Agent" value={manifest?.agent_id ?? "—"} mono />
          <MetaItem
            label="Status"
            value={<RunStatusBadge value={String(manifest?.status ?? "completed")} kind="status" />}
          />
          <MetaItem label="Steps" value={<span className="font-mono tabular-nums">{stepCount}</span>} />
          <MetaItem label="Task" value={manifest?.task_id ?? "—"} />
          <MetaItem label="Mode" value={manifest?.flight_mode ?? "record"} mono />
          <MetaItem label="Started" value={formatTimestamp(manifest?.started_at)} />
          <MetaItem label="Completed" value={formatTimestamp(manifest?.completed_at)} />
        </CardContent>
      </Card>

      {/* Timeline */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <ListTree className="h-4 w-4 text-muted-foreground" aria-hidden />
            Step timeline
            <span className="font-mono text-xs text-muted-foreground">({stepCount})</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {trace.length === 0 ? (
            <EmptyState
              Icon={FileWarning}
              title="No steps recorded"
              description="This run's manifest exists but no trace records were found. The cassette may still be uploading, or the recorder ran in passthrough mode."
            />
          ) : (
            <StepTimeline trace={trace} />
          )}
        </CardContent>
      </Card>
    </PageTransition>
  );
}
