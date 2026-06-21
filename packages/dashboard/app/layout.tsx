import type { Metadata } from "next";
import { Suspense } from "react";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { SiteHeader } from "@/components/sentinel/SiteHeader";

export const metadata: Metadata = {
  title: "Sentinel · AI Agent Reliability Platform",
  description:
    "Record, judge, and replay AI agent runs. Auditable verdicts with failure attribution for the Atlassian ecosystem.",
};

/**
 * Root layout: dark mission-control shell, Geist type (self-hosted via the geist
 * package, no remote font host), a fixed grain overlay, and the sticky nav.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen bg-canvas font-sans">
        {/* Page-wide grain. Fixed + non-interactive so it never repaints on scroll. */}
        <div
          className="grain pointer-events-none fixed inset-0 z-[1] opacity-[0.035]"
          aria-hidden
        />
        <div className="relative z-[2]">
          <Suspense fallback={null}>
            <SiteHeader />
          </Suspense>
          {children}
        </div>
      </body>
    </html>
  );
}
