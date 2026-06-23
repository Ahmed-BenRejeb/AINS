"use client";

import {
  Brain,
  Wrench,
  GitBranch,
  Camera,
  Clock,
  ArrowRight,
  Binary,
  MessagesSquare,
  Search,
  type LucideIcon,
} from "lucide-react";
import { motion, staggerContainer, staggerItem } from "./motion";
import {
  parseRetrievalAttributions,
  RetrievalAttribution,
} from "./RetrievalAttribution";
import type { TraceRecordRow } from "@/lib/types";
import { cn, truncate } from "@/lib/utils";

const KIND_META: Record<string, { label: string; Icon: LucideIcon; className: string }> = {
  // operation-level (preferred — derived from metadata_json.operation)
  embedding: {
    label: "embedding",
    Icon: Binary,
    className: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  chat: {
    label: "llm chat",
    Icon: MessagesSquare,
    className: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  },
  retrieval: {
    label: "vector search",
    Icon: Search,
    className: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  // kind-level (fallback)
  llm_call: {
    label: "llm call",
    Icon: Brain,
    className: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  },
  tool_call: {
    label: "tool call",
    Icon: Wrench,
    className: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  decision: {
    label: "decision",
    Icon: GitBranch,
    className: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
  state_snapshot: {
    label: "state snapshot",
    Icon: Camera,
    className: "border-hairline bg-white/[0.03] text-muted-foreground",
  },
};

/** Parse the `operation` + `model_id` a recorder stores in `metadata_json`. */
function parseMeta(json: string): { operation?: string; model_id?: string } {
  try {
    const m = JSON.parse(json) as { operation?: string; model_id?: string };
    return { operation: m.operation, model_id: m.model_id };
  } catch {
    return {};
  }
}

/** Short model name from a CF model id like `@cf/meta/llama-3.1-8b-instruct-fp8-fast`. */
function shortModel(modelId?: string): string | undefined {
  if (!modelId) return undefined;
  const parts = modelId.split("/");
  return parts[parts.length - 1] || modelId;
}

function KindBadge({ kind }: { kind: string }) {
  const meta = KIND_META[kind] ?? KIND_META.llm_call;
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
      {steps.map((step, i) => {
        const meta = parseMeta(step.metadata_json);
        // Prefer the operation label when it's a known badge; else fall back to kind.
        const badgeKey =
          meta.operation && meta.operation in KIND_META ? meta.operation : String(step.kind);
        const model = shortModel(meta.model_id);
        const retrievalAttributions = parseRetrievalAttributions(step.metadata_json);
        return (
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
                <div className="flex flex-wrap items-center gap-2">
                  <KindBadge kind={badgeKey} />
                  {model && (
                    <span className="font-mono text-[11px] text-muted-foreground">{model}</span>
                  )}
                </div>
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
                    {truncate(step.input_preview, 180) || "-"}
                  </code>
                </div>
                <div className="flex gap-2">
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                  <code className="block flex-1 break-words font-mono text-xs leading-relaxed text-emerald-200/80">
                    {truncate(step.output_preview, 180) || "-"}
                  </code>
                </div>
              </div>

              {retrievalAttributions && retrievalAttributions.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    XQdrant explainability
                  </p>
                  {retrievalAttributions.map((entry) => (
                    <RetrievalAttribution key={entry.id} entry={entry} />
                  ))}
                </div>
              )}
            </div>
          </motion.li>
        );
      })}
    </motion.ol>
  );
}
