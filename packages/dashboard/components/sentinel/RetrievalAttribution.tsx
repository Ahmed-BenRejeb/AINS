"use client";

import { cn } from "@/lib/utils";
import { resolveRetrievalTerms, sortedTermEntries } from "@/lib/resolve-retrieval-terms";

const AMBIGUOUS_MARGIN = 0.05;

export interface RetrievalAttributionEntry {
  id: string;
  score: number;
  dims: Record<string, number>;
  /** Concept-label contributions resolved by atlassian-remote (preferred). */
  terms?: Record<string, number>;
  /** Dimension ids with no entry in dimension_labels.json. */
  unmapped_dims?: string[];
  confidence_margin: number;
}

/**
 * XQdrant dimension-contribution breakdown for one retrieval hit.
 * Shows mapped SRE concept labels when available; surfaces unmapped dims as a gap.
 */
export function RetrievalAttribution({
  entry,
  className,
}: {
  entry: RetrievalAttributionEntry;
  className?: string;
}) {
  const ambiguous = entry.confidence_margin < AMBIGUOUS_MARGIN;

  const resolved =
    entry.terms && Object.keys(entry.terms).length > 0
      ? { terms: entry.terms, unmappedDims: entry.unmapped_dims ?? [] }
      : resolveRetrievalTerms(entry.dims);

  const termEntries = sortedTermEntries(resolved.terms).slice(0, 5);
  const unmapped = resolved.unmappedDims;
  const hasDims = Object.keys(entry.dims).length > 0;
  const maxContribution = termEntries[0]?.[1] ?? 1;

  if (!hasDims && termEntries.length === 0) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        <span className="font-mono">{entry.id}</span>
        <span className="text-muted-foreground/70"> · score {entry.score.toFixed(3)}</span>
        {ambiguous && (
          <span className="ml-2 rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-amber-200/90">
            ambiguous match
          </span>
        )}
      </p>
    );
  }

  return (
    <div className={cn("space-y-2 rounded-md border border-hairline bg-white/[0.02] p-3", className)}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <span className="font-mono font-medium text-foreground">{entry.id}</span>
        <span className="text-muted-foreground">score {entry.score.toFixed(3)}</span>
        <span className="text-muted-foreground">margin {entry.confidence_margin.toFixed(2)}</span>
        {ambiguous && (
          <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-amber-200/90">
            ambiguous
          </span>
        )}
      </div>

      {termEntries.length > 0 ? (
        <ul className="space-y-1.5">
          {termEntries.map(([label, contribution]) => (
            <li key={label} className="flex items-center gap-2 text-xs">
              <span className="min-w-0 flex-1 truncate text-foreground/90" title={label}>
                {label}
              </span>
              <div className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-sky-400/70"
                  style={{
                    width: `${Math.max(8, (Math.abs(contribution) / Math.abs(maxContribution)) * 100)}%`,
                  }}
                />
              </div>
              <span className="w-12 shrink-0 text-right font-mono tabular-nums text-foreground/80">
                {contribution.toFixed(3)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-amber-200/90">No concept mapping for this hit&apos;s dimensions.</p>
      )}

      {unmapped.length > 0 && (
        <p className="text-xs text-amber-200/80">
          Unmapped dims (not in label map):{" "}
          <span className="font-mono">{unmapped.map((d) => `d${d}`).join(", ")}</span>
        </p>
      )}

      {termEntries.length > 0 && hasDims && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">Raw dimensions</summary>
          <ul className="mt-1.5 space-y-0.5 font-mono">
            {Object.entries(entry.dims)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 5)
              .map(([dim, contribution]) => (
                <li key={dim}>
                  d{dim} = {contribution.toFixed(3)}
                </li>
              ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** Parse retrieval attributions stored in a trace step's ``metadata_json``. */
export function parseRetrievalAttributions(
  metadataJson: string,
): RetrievalAttributionEntry[] | null {
  try {
    const meta = JSON.parse(metadataJson) as {
      operation?: string;
      attributions?: RetrievalAttributionEntry[];
    };
    if (meta.operation !== "retrieval" || !Array.isArray(meta.attributions)) {
      return null;
    }
    return meta.attributions.filter(
      (entry) => entry && typeof entry.id === "string" && entry.dims,
    );
  } catch {
    return null;
  }
}
