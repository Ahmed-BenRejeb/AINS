import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

/** 404 — keep the dark shell and offer a way back. */
export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-hairline bg-card px-6 py-20 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-hairline bg-white/[0.02]">
        <Compass className="h-5 w-5 text-muted-foreground" aria-hidden />
      </div>
      <h2 className="text-lg font-semibold text-foreground">Page not found</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        That route doesn&apos;t exist. Head back to the overview to see runs and verdicts.
      </p>
      <Link href="/">
        <Button>Back to overview</Button>
      </Link>
    </div>
  );
}
