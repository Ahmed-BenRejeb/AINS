"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { EASE_OUT } from "./motion";
import { cn } from "@/lib/utils";

/**
 * Circular reliability gauge. The arc draws on first view and the center number
 * counts up to match. Color follows the value (emerald / amber / red) so it
 * doubles as a verdict signal. Decorative-but-motivated: it communicates the
 * single most important number (pass rate) at a glance.
 */
export function ReliabilityRing({
  value,
  size = 168,
  stroke = 10,
  label = "Pass rate",
  className,
}: {
  value: number; // 0..1
  size?: number;
  stroke?: number;
  label?: string;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(1, value));
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  // Default to the real value so the gauge is never blank if the count-up does not run.
  const [display, setDisplay] = useState(clamped);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color =
    clamped >= 0.75 ? "#34E5B0" : clamped >= 0.5 ? "#F5B445" : "#FB5E6D";

  useEffect(() => {
    if (!inView) return;
    let raf = 0;
    const start = performance.now();
    const dur = 1100;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      // ease-out-expo
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      setDisplay(clamped * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, clamped]);

  return (
    <div className={cn("relative inline-grid place-items-center", className)}>
      <svg ref={ref} width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#1E2427"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - clamped) }}
          transition={{ duration: 1.1, ease: EASE_OUT }}
          style={{ filter: `drop-shadow(0 0 6px ${color}55)` }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span
          className="font-mono text-3xl font-semibold tabular-nums"
          style={{ color }}
        >
          {Math.round(display * 100)}%
        </span>
        <span className="mt-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
      </div>
    </div>
  );
}
