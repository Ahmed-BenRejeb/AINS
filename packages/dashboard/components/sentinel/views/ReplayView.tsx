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
  Film,
  FlaskConical,
} from "lucide-react";
import { PageTransition, motion } from "../motion";
import { PageHeader } from "../PageHeader";
import { StepTimeline } from "../StepTimeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { BisectResult, Loaded, ReplayResult, RunDetail } from "@/lib/types";
import { cn, truncateId, withMock } from "@/lib/utils";

/**
 * Replay screen: shows the recorded trajectory that replay re-executes, the replay
 * deep-link, launches a deterministic replay (`POST /api/replay`) and a two-run
 * bisect (`POST /api/bisect`), and renders the result (clean replay / divergences,
 * or the first diverging step). `mock` is threaded to the API routes so demo mode
 * returns fixtures.
 */
export function ReplayView({
  runId,
  replayLink,
  detail,
  mock,
}: {
  runId: string;
  replayLink: string;
  detail?: RunDetail;
  mock: boolean;
}) {
  const [replay, setReplay] = useState<Loaded<ReplayResult> | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);

  const [goodRun, setGoodRun] = useState(runId);
  const [badRun, setBadRun] = useState("");
  const [bisect, setBisect] = useState<Loaded<BisectResult> | null>(null);
  const [bisectLoading, setBisectLoading] = useState(false);

  // Divergence editing (UC2 §3.4): override a recorded step's response mid-replay.
  const httpSteps = (detail?.trace ?? []).filter((s) => String(s.kind) === "llm_call");
  const [injectStep, setInjectStep] = useState(0);
  const [injectText, setInjectText] = useState('{"result": {"response": "INJECTED override"}}');
  const [inject, setInject] = useState<Loaded<ReplayResult> | null>(null);
  const [injectLoading, setInjectLoading] = useState(false);
  const [injectError, setInjectError] = useState<string | null>(null);

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

  async function launchInject() {
    setInjectError(null);
    let body: unknown;
    try {
      body = JSON.parse(injectText);
    } catch {
      setInjectError("Override must be valid JSON (the response body the model returns).");
      return;
    }
    setInjectLoading(true);
    setInject(null);
    try {
      const override = {
        status_code: 200,
        headers: { "content-type": "application/json" },
        is_json: true,
        body,
      };
      const res = await fetch("/api/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, mock, inject: { [injectStep]: override } }),
      });
      setInject((await res.json()) as Loaded<ReplayResult>);
    } finally {
      setInjectLoading(false);
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

      {/* Recorded trajectory — what replay re-executes */}
      {detail && detail.trace.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Film className="h-4 w-4 text-muted-foreground" aria-hidden />
              Recorded trajectory
              <span className="ml-1 font-mono text-xs font-normal text-muted-foreground">
                {detail.trace.length} steps
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-relaxed text-muted-foreground">
              These are the exact steps on tape. Launching replay re-executes them from the
              cassette and verifies each against its hash-chained audit record, hitting{" "}
              <span className="font-medium text-foreground">no live APIs</span>.
            </p>
            {detail.manifest && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Cassette" value={detail.manifest.cassette_id ? "stored" : "-"} />
                <Stat label="Steps" value={String(detail.manifest.step_count)} />
                <Stat label="Mode" value={detail.manifest.flight_mode} />
                <Stat label="Status" value={detail.manifest.status} />
              </div>
            )}
            <StepTimeline trace={detail.trace} />
          </CardContent>
        </Card>
      )}

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

      {/* Divergence editing — inject a modified response mid-replay */}
      {httpSteps.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-muted-foreground" aria-hidden />
              Divergence editing (inject during replay)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-relaxed text-muted-foreground">
              Override a recorded model response and replay. The override is served from the harness
              instead of the tape, with{" "}
              <span className="font-medium text-foreground">zero live API calls</span>. If the agent
              branches on this value it takes a new path (an unrecorded request shows up as a
              divergence); on a run whose model calls are independent the override is served and the
              run still completes, proving the inject hook.
            </p>
            <div className="grid gap-3 sm:grid-cols-[200px_1fr]">
              <label className="space-y-1.5">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Step to override
                </span>
                <select
                  value={injectStep}
                  onChange={(e) => setInjectStep(Number(e.target.value))}
                  className="w-full rounded-md border border-hairline bg-canvas px-3 py-2 font-mono text-xs text-foreground outline-none focus:border-white/25"
                >
                  {httpSteps.map((_, i) => (
                    <option key={i} value={i}>
                      step {i} ({i === httpSteps.length - 1 ? "RCA / chat" : "embedding"})
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1.5">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Override response (JSON)
                </span>
                <textarea
                  value={injectText}
                  onChange={(e) => setInjectText(e.target.value)}
                  spellCheck={false}
                  rows={2}
                  className="w-full rounded-md border border-hairline bg-canvas px-3 py-2 font-mono text-xs text-foreground outline-none focus:border-white/25"
                />
              </label>
            </div>
            <Button onClick={launchInject} disabled={injectLoading} variant="secondary">
              {injectLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <FlaskConical className="h-4 w-4" aria-hidden />
              )}
              {injectLoading ? "Injecting…" : "Inject & replay"}
            </Button>
            {injectError && <p className="text-xs text-verdict-fail">{injectError}</p>}
            {inject && <ReplayResultPanel result={inject} />}
          </CardContent>
        </Card>
      )}

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
            Regression triage for agent behaviour. Paste{" "}
            <span className="font-medium text-foreground">two different run ids</span> (the same id
            on both sides is always identical).
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
                placeholder="paste a different run id"
                className="w-full rounded-md border border-hairline bg-canvas px-3 py-2 font-mono text-xs text-foreground outline-none transition-colors placeholder:text-muted-foreground/50 focus:border-white/25"
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
      {r.injected_steps && r.injected_steps.length > 0 && (
        <p className="flex items-center gap-1.5 text-xs text-amber-300/90">
          <FlaskConical className="h-3.5 w-3.5" aria-hidden />
          Overrode step{r.injected_steps.length === 1 ? "" : "s"} {r.injected_steps.join(", ")} during
          replay (served from the harness, not the tape).
        </p>
      )}
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

/** Pretty-print a step output, capped so a 768-dim embedding vector can't flood the UI. */
function previewOutput(output: unknown): string {
  const json = JSON.stringify(output, null, 2);
  if (json === undefined) return "-";
  return json.length > 600 ? `${json.slice(0, 600)}\n… (truncated)` : json;
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
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-white/[0.03] p-2 font-mono text-[11px] text-foreground/80">
                {previewOutput(b.good_output)}
              </pre>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-verdict-fail">Bad</div>
              <div className="mt-1 font-mono text-xs text-muted-foreground">
                {truncateId(b.bad_run_id, 12)} · {b.bad_step_key ?? "-"}
              </div>
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-white/[0.03] p-2 font-mono text-[11px] text-foreground/80">
                {previewOutput(b.bad_output)}
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
