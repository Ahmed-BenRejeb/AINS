import { Radio, FlaskConical, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DataSource } from "@/lib/types";

const CONFIG: Record<
  DataSource,
  { label: string; variant: "pass" | "neutral" | "uncertain"; Icon: typeof Radio }
> = {
  live: { label: "LIVE", variant: "pass", Icon: Radio },
  mock: { label: "MOCK DATA", variant: "neutral", Icon: FlaskConical },
  "mock-fallback": { label: "MOCK (fallback)", variant: "uncertain", Icon: TriangleAlert },
};

/**
 * Honesty badge: tells the viewer whether the data on screen is live, explicitly
 * mocked (`?mock=true`), or a fallback because a live service was unreachable.
 */
export function DataSourceBadge({
  source,
  title,
}: {
  source: DataSource;
  title?: string;
}) {
  const { label, variant, Icon } = CONFIG[source];
  return (
    <Badge variant={variant} className="tracking-wide" title={title}>
      <Icon className="h-3 w-3" aria-hidden />
      {label}
    </Badge>
  );
}
