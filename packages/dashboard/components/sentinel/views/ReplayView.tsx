"use client";

import { useState } from "react";
import {
  PlayCircle,
  GitCompareArrows,
  CheckCircle2,
  AlertTriangle,
  Link2,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { PageTransition, motion } from "../motion";
import { PageHeader } from "../PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { BisectResult, Loaded, ReplayResult } from "@/lib/types";
import { cn, truncateId, withMock } from "@/lib/utils";

/**
 * Replay screen: shows the replay deep-link, launches a deterministic replay
 * (`POST /api/replay`) and a two-run bisect (`POST /api/bisect`), and renders the
 * result (clean replay / divergences, or the first diverging step). `mock` is
 * threaded to the API routes so demo mode returns fixtures.
 */
export function ReplayView({
  runId,
  replayLink,
  mock,
}: {
  runId: string;
  replayLink: string;
  mock: boolean;
}) {
  const [replay, setReplay] = useState<Loaded<ReplayResult> | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);

  const [goodRun, setGoodRun] = useState(runId);
  const [badRun, setBadRun] = useState(runId);
  const [bisect, setBisect] = useState<Loaded<BisectResult> | null>(null);
  const [bisectLoading, setBisectLoading] = useState(false);

  async function launchReplay() {
    setReplayLoading(true);
    setReplay(null);
    try {
      const res = await fetch("/api/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, mock }),
      });
      setReplay((await res.json()) as Loaded<ReplayResult>);
    } finally {
      setReplayLoading(false);
    }
  }

  async function launchBisect() {
    setBisectLoading(true);
    setBisect(null);
    try {
      const res = await fetch("/api/bisect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ good_run_id: goodRun, bad_run_id: badRun, mock }),
      });
      setBisect((await res.json()) as Loaded<BisectResult>);
    } finally {
      setBisectLoading(false);
    }
  }

  return (
    <PageTransition className="mx-auto w-full max-w-[1180px] space-y-6 px-5 py-10 md:px-8">
      <PageHeader
        title="Deterministic replay"
        subtitle={<span className="font-mono">{runId}</span>}
        backHref={withMock(`/runs/${runId}`, mock)}
        backLabel="Back to trace"
      />

      {/* Replay link */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-muted-foreground" aria-hidden />
            Replay link
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            Replay re-drives this run against its recorded cassette. Every LLM and tool call is
            served from tape, so a clean replay makes{" "}
            <span className="font-medium text-foreground">zero live API calls</span>. It proves the
            run is reproducible and audit-stable.
          </p>
          <a
            href={replayLink}
            target="_blank"
            rel="noreferrer"
            className="block truncate rounded-md border border-hairline bg-canvas px-3 py-2 font-mono text-xs text-sky-300 transition-colors hover:border-white/15"
          >
            {replayLink}
          </a>
          <Button onClick={launchReplay} disabled={replayLoading} variant="emerald">
            {replayLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <PlayCircle className="h-4 w-4" aria-hidden />
            )}
            {replayLoading ? "Replaying…" : "Launch replay"}
          </Button>

          {replay && <ReplayResultPanel result={replay} />}
        </CardContent>
      </Card>

      {/* Bisect */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <GitCompareArrows className="h-4 w-4 text-muted-foreground" aria-hidden />
            Bisect two runs
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            Compare a known-good run against a known-bad one to find the first diverging step.
            Regression triage for agent behaviour.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1.5">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                Good run ID
              </span>
              <input
                value={goodRun}
                onChange={(e) => setGoodRun(e.target.value)}
                spellCheck={false}
                className="w-full rounded-md border border-hairline bg-canvas px-3 py-2 font-mono text-xs text-foreground outline-none transition-colors focus:border-white/25"
              />
            </label>
            <label className="space-y-1.5">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                Bad run ID
              </span>
              <input
                value={badRun}
                onChange={(e) => setBadRun(e.target.value)}
                spellCheck={false}
                className="w-full rounded-md border border-hairline bg-canvas px-3 py-2 font-mono text-xs text-foreground outline-none transition-colors focus:border-white/25"
              />
            </label>
          </div>
          <Button
            onClick={launchBisect}
            disabled={bisectLoading || !goodRun || !badRun}
            variant="secondary"
          >
            {bisectLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <GitCompareArrows className="h-4 w-4" aria-hidden />
            )}
            {bisectLoading ? "Bisecting…" : "Run bisect"}
          </Button>

          {bisect && <BisectResultPanel result={bisect} />}
        </CardContent>
      </Card>
    </PageTransition>
  );
}

function ResultBanner({
  ok,
  okText,
  badText,
}: {
  ok: boolean;
  okText: string;
  badText: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className={cn(
        "flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium",
        ok
          ? "border-verdict-pass/40 bg-verdict-pass/[0.08] text-verdict-pass"
          : "border-verdict-fail/40 bg-verdict-fail/[0.08] text-verdict-fail",
      )}
    >
      {ok ? (
        <CheckCircle2 className="h-4 w-4" aria-hidden />
      ) : (
        <AlertTriangle className="h-4 w-4" aria-hidden />
      )}
      {ok ? okText : badText}
    </motion.div>
  );
}

function ReplayResultPanel({ result }: { result: Loaded<ReplayResult> }) {
  const r = result.data;
  const clean = r.live_call_count === 0 && !r.diverged;
  return (
    <div className="space-y-3">
      <ResultBanner
        ok={clean}
        okText={`Replay complete. ${r.live_call_count} live API calls, ${r.recorded_steps} steps reproduced exactly.`}
        badText={`Replay diverged. ${r.divergences.length} divergence${r.divergences.length === 1 ? "" : "s"} detected.`}
      />
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Recorded steps" value={String(r.recorded_steps)} />
        <Stat
          label="Live API calls"
          value={String(r.live_call_count)}
          accent={r.live_call_count === 0 ? "text-verdict-pass" : "text-verdict-fail"}
        />
        <Stat
          label="Diverged"
          value={r.diverged ? "yes" : "no"}
          accent={r.diverged ? "text-verdict-fail" : "text-verdict-pass"}
        />
      </div>
      {r.divergences.length > 0 && (
        <div className="space-y-2">
          {r.divergences.map((d, i) => (
            <div key={i} className="rounded-md border border-verdict-fail/30 bg-verdict-fail/[0.05] p-3">
              <div className="font-mono text-xs text-verdict-fail">{d.step_key || "(unknown step)"}</div>
              <div className="mt-1 text-sm text-foreground/90">{d.reason}</div>
            </div>
          ))}
        </div>
      )}
      {clean && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 text-verdict-pass" aria-hidden />
          Hash-chained audit trail verified. The run is byte for byte reproducible.
        </p>
      )}
    </div>
  );
}

function BisectResultPanel({ result }: { result: Loaded<BisectResult> }) {
  const b = result.data;
  return (
    <div className="space-y-3">
      <ResultBanner
        ok={b.identical}
        okText="Runs are identical. No divergence found."
        badText={`First divergence at step ${b.first_diverging_step ?? "?"}.`}
      />
      {!b.identical && (
        <div className="rounded-md border border-hairline bg-canvas p-4">
          <div className="text-sm text-foreground/90">{b.reason}</div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="text-xs uppercase tracking-wide text-verdict-pass">Good</div>
              <div className="mt-1 font-mono text-xs text-muted-foreground">
                {truncateId(b.good_run_id, 12)} · {b.good_step_key ?? "-"}
              </div>
              <pre className="mt-1 overflow-x-auto rounded bg-white/[0.03] p-2 font-mono text-[11px] text-foreground/80">
                {JSON.stringify(b.good_output, null, 2)}
              </pre>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-verdict-fail">Bad</div>
              <div className="mt-1 font-mono text-xs text-muted-foreground">
                {truncateId(b.bad_run_id, 12)} · {b.bad_step_key ?? "-"}
              </div>
              <pre className="mt-1 overflow-x-auto rounded bg-white/[0.03] p-2 font-mono text-[11px] text-foreground/80">
                {JSON.stringify(b.bad_output, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-md border border-hairline bg-canvas px-3 py-2.5">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={cn("mt-1 font-mono text-xl font-semibold tabular-nums text-foreground", accent)}>
        {value}
      </div>
    </div>
  );
}
