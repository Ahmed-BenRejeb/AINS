import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names, resolving conflicts (shadcn convention). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Append `?mock=true` to a path when mock mode is active, so links keep the flag. */
export function withMock(href: string, mock: boolean): string {
  if (!mock) return href;
  return href.includes("?") ? `${href}&mock=true` : `${href}?mock=true`;
}

/** Truncate an identifier to its first `n` characters (default 8) for display. */
export function truncateId(id: string | null | undefined, n = 8): string {
  if (!id) return "-";
  return id.length <= n ? id : id.slice(0, n);
}

/** Truncate free text to `n` characters with an ellipsis. */
export function truncate(text: string | null | undefined, n = 100): string {
  if (!text) return "";
  return text.length <= n ? text : `${text.slice(0, n).trimEnd()}…`;
}

/** Format a 0–1 ratio as a whole-number percentage string, e.g. "82%". */
export function pct(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "-";
  return `${Math.round(ratio * 100)}%`;
}

/** Format an ISO timestamp as a compact, locale-stable absolute string. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** Relative "time ago" for recency cues; falls back to absolute on parse failure. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const seconds = Math.round((Date.now() - d.getTime()) / 1000);
  const ranges: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [60 * 60, "minute"],
    [60 * 60 * 24, "hour"],
    [60 * 60 * 24 * 30, "day"],
    [60 * 60 * 24 * 365, "month"],
    [Infinity, "year"],
  ];
  const divisors = [1, 60, 60 * 60, 60 * 60 * 24, 60 * 60 * 24 * 30, 60 * 60 * 24 * 365];
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (let i = 0; i < ranges.length; i++) {
    if (Math.abs(seconds) < ranges[i][0]) {
      const value = Math.round(seconds / divisors[i]);
      return rtf.format(-value, ranges[i][1]);
    }
  }
  return formatTimestamp(iso);
}
