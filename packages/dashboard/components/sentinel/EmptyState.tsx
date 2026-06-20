import type { LucideIcon } from "lucide-react";

/**
 * Helpful empty state — never a blank panel. Always pairs an icon with a short
 * explanation and, ideally, the next action (e.g. "try ?mock=true").
 */
export function EmptyState({
  Icon,
  title,
  description,
  action,
}: {
  Icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-hairline bg-card/40 px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-hairline bg-white/[0.02]">
        <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
      </div>
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
