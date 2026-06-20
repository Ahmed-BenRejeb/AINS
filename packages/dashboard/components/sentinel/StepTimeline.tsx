"use client";

import { Brain, Wrench, GitBranch, Camera, Clock, ArrowRight, type LucideIcon } from "lucide-react";
import { motion, staggerContainer, staggerItem } from "./motion";
import { Badge } from "@/components/ui/badge";
import type { TraceRecordRow } from "@/lib/types";
import { cn, truncate } from "@/lib/utils";

const KIND_META: Record<string, { label: string; Icon: LucideIcon; className: string }> = {
  llm_call: {
    label: "llm_call",
    Icon: Brain,
    className: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  },
  tool_call: {
    label: "tool_call",
    Icon: Wrench,
    className: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  decision: {
    label: "decision",
    Icon: GitBranch,
    className: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
  state_snapshot: {
    label: "state_snapshot",
    Icon: Camera,
    className: "border-hairline bg-white/[0.03] text-muted-foreground",
  },
};

function KindBadge({ kind }: { kind: string }) {
  const meta = KIND_META[kind] ?? KIND_META.state_snapshot;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-xs",
        meta.className,
      )}
    >
      <meta.Icon className="h-3.5 w-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}

/**
 * Vertical execution timeline. Each step fades in with a 0.05s stagger and shows
 * its kind, latency, and truncated input/output previews. The sequence index sits
 * on a connecting rail so the run reads top-to-bottom as a story.
 */
export function StepTimeline({ trace }: { trace: TraceRecordRow[] }) {
  const steps = [...trace].sort((a, b) => a.sequence - b.sequence);

  return (
    <motion.ol variants={staggerContainer} initial="hidden" animate="show" className="relative">
      {steps.map((step, i) => (
        <motion.li key={step.id ?? i} variants={staggerItem} className="relative flex gap-4 pb-6 last:pb-0">
          {/* Rail + node */}
          <div className="relative flex flex-col items-center">
            <div className="z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-hairline bg-card font-mono text-xs text-muted-foreground">
              {step.sequence}
            </div>
            {i < steps.length - 1 && (
              <span className="absolute top-8 h-full w-px bg-hairline" aria-hidden />
            )}
          </div>

          {/* Step card */}
          <div className="flex-1 rounded-lg border border-hairline bg-card p-4 transition-colors hover:border-white/15">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <KindBadge kind={String(step.kind)} />
              {typeof step.latency_ms === "number" && (
                <span className="inline-flex items-center gap-1 font-mono text-xs tabular-nums text-muted-foreground">
                  <Clock className="h-3 w-3" aria-hidden />
                  {step.latency_ms} ms
                </span>
              )}
            </div>

            <div className="mt-3 space-y-2 text-sm">
              <div className="flex gap-2">
                <span className="mt-0.5 select-none text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  in
                </span>
                <code className="block flex-1 break-words font-mono text-xs leading-relaxed text-foreground/80">
                  {truncate(step.input_preview, 100) || "—"}
                </code>
              </div>
              <div className="flex gap-2">
                <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                <code className="block flex-1 break-words font-mono text-xs leading-relaxed text-emerald-200/80">
                  {truncate(step.output_preview, 100) || "—"}
                </code>
              </div>
            </div>
          </div>
        </motion.li>
      ))}
    </motion.ol>
  );
}
