"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ShieldCheck, FlaskConical, ExternalLink } from "lucide-react";
import { LANGFUSE_URL } from "@/lib/api";
import { cn, withMock } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/runs", label: "Runs" },
];

/**
 * Persistent top navigation. Active-route aware, and it threads the `?mock=true`
 * flag through every internal link + exposes a toggle, so demo mode survives
 * navigation. Langfuse opens the trace UI in a new tab.
 */
export function SiteHeader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const mock = searchParams.get("mock") === "true" || searchParams.get("mock") === "1";

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-canvas/80 backdrop-blur supports-[backdrop-filter]:bg-canvas/60">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-6 md:px-8">
        <Link href={withMock("/", mock)} className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md border border-hairline bg-card">
            <ShieldCheck className="h-4 w-4 text-verdict-pass" aria-hidden />
          </span>
          <span className="text-sm font-semibold tracking-tight text-foreground">Sentinel</span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={withMock(item.href, mock)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                isActive(item.href)
                  ? "bg-white/[0.06] text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <a
            href={LANGFUSE_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:flex"
          >
            Langfuse
            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          </a>
          <Link
            href={mock ? pathname : withMock(pathname, true)}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
              mock
                ? "border-verdict-uncertain/40 bg-verdict-uncertain/10 text-verdict-uncertain"
                : "border-hairline text-muted-foreground hover:text-foreground",
            )}
            title={mock ? "Showing fixture data — click to use live services" : "Switch to fixture data"}
          >
            <FlaskConical className="h-3.5 w-3.5" aria-hidden />
            {mock ? "Mock mode on" : "Mock mode"}
          </Link>
        </div>
      </div>
    </header>
  );
}
