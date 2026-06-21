import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { DataSourceBadge } from "./DataSourceBadge";
import type { DataSource } from "@/lib/types";

/**
 * Consistent page heading: an optional back link, a title (with optional monospace
 * subtitle for ids), and the data-source badge pinned to the right.
 */
export function PageHeader({
  title,
  subtitle,
  source,
  sourceError,
  backHref,
  backLabel,
  actions,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  source?: DataSource;
  sourceError?: string;
  backHref?: string;
  backLabel?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8">
      {backHref && (
        <Link
          href={backHref}
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          {backLabel ?? "Back"}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-[-0.02em] text-foreground">{title}</h1>
          {subtitle && <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {source && (
            <DataSourceBadge
              source={source}
              title={sourceError ? `Live fetch failed: ${sourceError}` : undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
}
