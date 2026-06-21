import { cn } from "@/lib/utils";

// Geometry from the uploaded sentinel_logo.svg (a geometric hexagon shield with a
// single sentinel dot + top notch). Reproduced as an inline, themeable component so
// it can take on the page's colors and animate. The shield uses currentColor; the
// dot carries the emerald signal.
const OUTER = "M0,-72 L56,-36 L56,20 L0,60 L-56,20 L-56,-36 Z";
const INNER = "M0,-54 L42,-27 L42,15 L0,45 L-42,15 L-42,-27 Z";

/** The Sentinel hex-shield mark. Inherits text color; dot is the emerald signal. */
export function SentinelMark({
  className,
  strokeWidth = 5,
}: {
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg viewBox="-64 -80 128 152" fill="none" className={className} aria-hidden>
      <path d={OUTER} stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin="round" />
      <path
        d={INNER}
        stroke="currentColor"
        strokeWidth={strokeWidth * 0.4}
        strokeLinejoin="round"
        opacity={0.35}
      />
      <line
        x1={-10}
        y1={-54}
        x2={10}
        y2={-54}
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <circle cx={0} cy={4} r={9} className="fill-accent" />
    </svg>
  );
}

/**
 * Large hero emblem: the shield with a slow radar sweep clipped inside it and a
 * breathing signal dot. The single "sentinel watching" device for the page. Pure
 * CSS animation (off the main thread); collapses to static under reduced motion.
 */
export function SentinelEmblem({ className }: { className?: string }) {
  return (
    <svg viewBox="-80 -96 160 184" fill="none" className={cn("overflow-visible", className)} aria-hidden>
      <defs>
        <clipPath id="hexclip">
          <path d={OUTER} />
        </clipPath>
        <linearGradient id="sweep" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#34E5B0" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#34E5B0" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="coreglow" cx="50%" cy="55%" r="50%">
          <stop offset="0%" stopColor="#34E5B0" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#34E5B0" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* inner glow */}
      <path d={OUTER} fill="url(#coreglow)" />

      {/* radar sweep, clipped to the shield; spins about the shield centre */}
      <g clipPath="url(#hexclip)">
        <g
          className="motion-safe:animate-[spin_6s_linear_infinite]"
          style={{ transformBox: "view-box", transformOrigin: "0px 4px" }}
        >
          <polygon points="0,4 64,-92 -64,-92" fill="url(#sweep)" />
        </g>
      </g>

      {/* shield outlines */}
      <path d={OUTER} stroke="currentColor" strokeWidth={2.5} strokeLinejoin="round" />
      <path d={INNER} stroke="currentColor" strokeWidth={1} strokeLinejoin="round" opacity={0.3} />
      <line x1={-10} y1={-54} x2={10} y2={-54} stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" />

      {/* breathing signal dot */}
      <circle cx={0} cy={4} r={6} className="fill-accent motion-safe:animate-pulse-ring" />
      <circle cx={0} cy={4} r={6} className="fill-accent" />
    </svg>
  );
}

/** Mark + SENTINEL wordmark lockup, for the footer / compact brand placements. */
export function SentinelLockup({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <SentinelMark className="h-6 w-6 text-foreground" />
      <span className="text-[15px] font-semibold tracking-[-0.01em]">Sentinel</span>
    </div>
  );
}
