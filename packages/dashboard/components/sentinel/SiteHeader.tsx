"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ArrowUpRight, FlaskConical } from "lucide-react";
import { SentinelMark } from "./Logo";
import { LANGFUSE_URL } from "@/lib/api";
import { cn, withMock } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/runs", label: "Runs" },
  { href: "/reliability", label: "Reliability" },
];

/**
 * Sticky glass navigation. One line, 64px tall, single emerald accent. Threads the
 * `?mock=true` flag through every internal link and a toggle, so demo mode survives
 * navigation. Glass is used purposefully here (a floating bar over scrolling
 * content), not as page-wide decoration.
 */
export function SiteHeader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const mock = searchParams.get("mock") === "true" || searchParams.get("mock") === "1";
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-40 border-b border-hairline/80 bg-canvas/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-[1180px] items-center gap-6 px-5 md:px-8">
        <Link href={withMock("/", mock)} className="group flex items-center gap-2.5">
          <SentinelMark className="h-7 w-7 text-foreground transition-transform duration-300 ease-out group-hover:scale-105" />
          <span className="font-display text-[17px] font-semibold tracking-[-0.01em]">Sentinel</span>
        </Link>

        <nav className="hidden items-center gap-1 sm:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={withMock(item.href, mock)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors duration-200 ease-out",
                isActive(item.href)
                  ? "text-foreground"
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
            className="hidden items-center gap-1 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors duration-200 ease-out hover:text-foreground md:inline-flex"
          >
            Langfuse
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </a>
          <Link
            href={mock ? pathname : withMock(pathname, true)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors duration-200 ease-out",
              mock
                ? "border-verdict-uncertain/40 bg-verdict-uncertain/10 text-verdict-uncertain"
                : "border-hairline text-muted-foreground hover:border-hairline-strong hover:text-foreground",
            )}
            title={mock ? "Showing fixture data. Click to use live services." : "Switch to fixture data"}
          >
            <FlaskConical className="h-3.5 w-3.5" aria-hidden />
            {mock ? "Mock" : "Live"}
          </Link>
          <Link
            href={withMock("/runs", mock)}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-accent-ink transition-transform duration-150 ease-out hover:bg-[#43efba] active:scale-[0.97]"
          >
            Open console
          </Link>
        </div>
      </div>
    </header>
  );
}
