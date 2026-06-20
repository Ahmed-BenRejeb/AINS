import { cn } from "@/lib/utils";

/**
 * Loading placeholder with a left-to-right shimmer. Per the design spec, loading
 * states use skeletons, never spinners.
 */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-white/[0.04]",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-shimmer",
        "after:bg-gradient-to-r after:from-transparent after:via-white/[0.06] after:to-transparent",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
