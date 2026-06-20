import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { SiteHeader } from "@/components/sentinel/SiteHeader";

export const metadata: Metadata = {
  title: "Sentinel — AI Agent Reliability Platform",
  description:
    "Record, judge, and replay AI agent runs. Auditable verdicts with failure attribution for the Atlassian ecosystem.",
};

/**
 * Root layout: applies the dark canvas and the persistent top navigation.
 * Fonts use system stacks (declared in globals.css) so the build never depends on
 * a remote font host — children render inside a generously padded content column.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-canvas">
        <Suspense fallback={null}>
          <SiteHeader />
        </Suspense>
        <main className="mx-auto w-full max-w-6xl px-6 py-10 md:px-8">{children}</main>
      </body>
    </html>
  );
}
