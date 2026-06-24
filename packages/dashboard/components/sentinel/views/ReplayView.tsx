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
  // Default to the last http step (the chat/RCA step) — that's the meaningful one to override.
  const [injectStep, setInjectStep] = useState(() => Math.max(0, httpSteps.length - 1));
  const [injectText, setInjectText] = useState(
    '{"result": {"response": "{\\"root_cause_hypothesis\\": \\"INJECTED: disk I/O saturation on replica node caused replication lag\\", \\"confidence_score\\": 0.9, \\"proposed_severity\\": \\"critical\\"}"}}',
  );
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

  // The original RCA from the trace output_preview (for the inject before/after comparison)
  const originalRca =
    detail?.trace
      .filter((s) => String(s.kind) === "llm_call")
      .slice(-1)[0]?.output_preview ?? null;

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
              The full recorded workflow. <span className="font-medium text-foreground">HTTP steps</span>{" "}
              (embedding + chat) are stored in the cassette and replayed byte-for-byte hitting zero live
              APIs. Tool-call steps (vector search) are in the audit trail but are not HTTP calls, so
              they are not in the cassette and do not count toward the replay total.
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
              Swap a recorded model response and replay. Inject at the{" "}
              <span className="font-medium text-foreground">RCA / chat step</span> to see what the
              agent would have produced if the model had said something different. The result shows
              the original cassette output alongside your injected value so you can compare them
              directly.
            </p>
            {originalRca && (
              <div className="space-y-1.5">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Original recorded output (step {httpSteps.length - 1} — RCA)
                </div>
                <pre className="max-h-32 overflow-auto rounded bg-white/[0.03] p-2.5 font-mono text-[11px] text-foreground/70">
                  {originalRca.slice(0, 600)}
                  {originalRca.length > 600 ? "\n… (truncated)" : ""}
                </pre>
              </div>
            )}
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
                      step {i} — {i === httpSteps.length - 1 ? "RCA / chat ← best to inject here" : "embedding"}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1.5">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Injected model response (JSON body the model returns)
                </span>
                <textarea
                  value={injectText}
                  onChange={(e) => setInjectText(e.target.value)}
                  spellCheck={false}
                  rows={3}
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
            {inject && <ReplayResultPanel result={inject} injectedText={injectText} />}
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
            Compare two cassettes step by step to find the first diverging step. Best used with two
            runs that analyzed the{" "}
            <span className="font-medium text-foreground">same incident</span> but at different times
            or model versions — then divergence at step 1 (chat) means the LLM gave a different
            answer. Runs that analyzed different incidents will always diverge at step 0 (different
            embedding input), which is expected and not a bug.
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

function ReplayResultPanel({
  result,
  injectedText,
}: {
  result: Loaded<ReplayResult>;
  injectedText?: string;
}) {
  const r = result.data;
  const clean = r.live_call_count === 0 && !r.diverged;
  const hasInject = r.injected_steps && r.injected_steps.length > 0;
  return (
    <div className="space-y-3">
      <ResultBanner
        ok={clean}
        okText={`Replay complete. ${r.recorded_steps} HTTP steps served from cassette, 0 live API calls.`}
        badText={`Replay diverged. ${r.divergences.length} divergence${r.divergences.length === 1 ? "" : "s"} detected.`}
      />
      <div className="grid grid-cols-3 gap-3">
        <Stat label="HTTP steps (cassette)" value={String(r.recorded_steps)} />
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

      {/* Show the actual RCA output from the cassette */}
      {r.output_preview && !hasInject && (
        <div className="space-y-1.5">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Replayed agent output (RCA draft)
          </div>
          <pre className="max-h-48 overflow-auto rounded bg-white/[0.03] p-3 font-mono text-[11px] text-foreground/80">
            {r.output_preview}
          </pre>
        </div>
      )}

      {/* Inject: show before/after comparison */}
      {hasInject && (
        <div className="space-y-2">
          <p className="flex items-center gap-1.5 text-xs text-amber-300/90">
            <FlaskConical className="h-3.5 w-3.5" aria-hidden />
            Overrode step{r.injected_steps!.length === 1 ? "" : "s"} {r.injected_steps!.join(", ")} —
            served from the harness instead of the tape.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {r.original_outputs &&
              r.injected_steps!.map((stepIdx) => {
                const orig = (r.original_outputs as Record<string, string>)[String(stepIdx)];
                if (!orig) return null;
                return (
                  <div key={stepIdx}>
                    <div className="mb-1 text-xs text-muted-foreground">
                      Original cassette (step {stepIdx})
                    </div>
                    <pre className="max-h-40 overflow-auto rounded bg-white/[0.03] p-2.5 font-mono text-[11px] text-foreground/70">
                      {orig}
                    </pre>
                  </div>
                );
              })}
            {injectedText && (
              <div>
                <div className="mb-1 text-xs text-amber-300/80">Your injected value</div>
                <pre className="max-h-40 overflow-auto rounded bg-amber-400/[0.04] border border-amber-400/20 p-2.5 font-mono text-[11px] text-foreground/80">
                  {injectedText.slice(0, 600)}
                </pre>
              </div>
            )}
          </div>
        </div>
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
      {clean && !hasInject && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 text-verdict-pass" aria-hidden />
          Hash-chained audit trail verified. The run is byte for byte reproducible.
        </p>
      )}
    </div>
  );
}

/**
 * Pretty-print a step output for the bisect diff panel.
 * Detects CF Workers AI embedding responses (body.result.data is a float[][]) and
 * replaces the raw vectors with a concise summary so the panel stays readable.
 */
function previewOutput(output: unknown): string {
  if (output && typeof output === "object") {
    const out = output as Record<string, unknown>;
    // Cassette step entry: {status_code, is_json, body: {result: {data: float[][]}}}
    const body = out.body as Record<string, unknown> | undefined;
    const result = body?.result as Record<string, unknown> | undefined;
    if (Array.isArray(result?.data)) {
      const vecs = result.data as unknown[][];
      const dims = Array.isArray(vecs[0]) ? vecs[0].length : "?";
      return `embedding: ${vecs.length} vector(s), ${dims}-dim\n(raw floats omitted for readability)`;
    }
    // Chat response: body.result.response is a string
    if (typeof result?.response === "string") {
      return `chat response:\n${result.response.slice(0, 400)}${result.response.length > 400 ? "\n… (truncated)" : ""}`;
    }
  }
  const json = JSON.stringify(output, null, 2);
  if (json === undefined) return "-";
  return json.length > 600 ? `${json.slice(0, 600)}\n… (truncated)` : json;
}

function BisectResultPanel({ result }: { result: Loaded<BisectResult> }) {
  const b = result.data;
  const requestDiverge = b.reason === "request diverged (different step_key)";
  return (
    <div className="space-y-3">
      <ResultBanner
        ok={b.identical}
        okText="Runs are identical. No divergence found."
        badText={`First divergence at step ${b.first_diverging_step ?? "?"}.`}
      />
      {!b.identical && (
        <div className="rounded-md border border-hairline bg-canvas p-4 space-y-3">
          <div className="text-sm text-foreground/90">{b.reason}</div>
          {requestDiverge && (
            <p className="text-xs text-muted-foreground border-l-2 border-accent/40 pl-3">
              Step {b.first_diverging_step} had different inputs (different incident text → different
              embedding hash). To see a response-level divergence, compare two runs that analyzed the
              same incident. The RCA outputs below are always compared regardless.
            </p>
          )}
        </div>
      )}

      {/* Always show the RCA comparison — this is the meaningful diff */}
      {(b.good_rca || b.bad_rca) && (
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            RCA output comparison (chat step)
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-xs text-verdict-pass">
                Good run · {truncateId(b.good_run_id, 12)}
              </div>
              <pre className="max-h-64 overflow-auto rounded bg-verdict-pass/[0.04] border border-verdict-pass/20 p-3 font-mono text-[11px] text-foreground/80">
                {b.good_rca ?? "(no chat step found)"}
              </pre>
            </div>
            <div>
              <div className="mb-1 text-xs text-verdict-fail">
                Bad run · {truncateId(b.bad_run_id, 12)}
              </div>
              <pre className="max-h-64 overflow-auto rounded bg-verdict-fail/[0.04] border border-verdict-fail/20 p-3 font-mono text-[11px] text-foreground/80">
                {b.bad_rca ?? "(no chat step found)"}
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
