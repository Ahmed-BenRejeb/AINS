"use client";

import Link from "next/link";
import { TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Last-resort error boundary. */
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-hairline bg-card px-6 py-20 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-verdict-fail/40 bg-verdict-fail/10">
        <TriangleAlert className="h-5 w-5 text-verdict-fail" aria-hidden />
      </div>
      <h2 className="text-lg font-semibold text-foreground">Something went wrong</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        The page hit an unexpected error. Please retry, or head back to the overview.
      </p>
      <div className="flex gap-2">
        <Button onClick={reset} variant="secondary">
          Try again
        </Button>
        <Link href="/">
          <Button>Back to overview</Button>
        </Link>
      </div>
    </div>
  );
}
